"""Bounded sandbox fan-out and artifact handoff owned by the coordinator."""

import asyncio
import json
import time
from pathlib import Path

from nebius_sandbox import ExecutionFailed, OperationFailed

from .agents import log
from .artifacts import retrieve_result
from .models import Receipt
from .sandbox import submit_worker, upload_code


class SandboxExecution:
    def __init__(self, api, config, child_env, root=Path("/app")):
        self.api, self.config, self.env, self.root = api, config, child_env, root
        self.active = set()
        self.jobs = []
        self.code = None
        self.inputs = {}

    async def upload_json(self, value):
        return await asyncio.to_thread(self.api.upload, json.dumps(value).encode())

    async def prepare(self, sources):
        self.code = await asyncio.to_thread(upload_code, self.api, self.root)
        for source in sources:
            self.inputs[source["path"]] = await asyncio.to_thread(
                self.api.upload, Path(source["path"]).read_bytes()
            )

    async def cancel(self, operation):
        try:
            await asyncio.to_thread(self.api.cancel, operation)
            log("child.cancel_requested", operation_id=operation)
        except Exception:
            log("child.cancel_unconfirmed", operation_id=operation)
        finally:
            self.active.discard(operation)

    async def close(self):
        await asyncio.gather(*(self.cancel(op) for op in list(self.active)))

    async def job(self, role, files, receipt_id=None):
        files = dict(self.code, **files)
        files["/app/workflow.json"] = await self.upload_json({"role": role})
        timeout = self.config["child_timeout"]
        # Shield submission: if cancelled during POST, retain its returned ID for cleanup.
        submission = asyncio.create_task(
            asyncio.to_thread(
                submit_worker,
                self.api,
                self.config["image"],
                files,
                self.env,
                timeout,
            )
        )
        try:
            operation = await asyncio.shield(submission)
        except asyncio.CancelledError:
            try:
                self.active.add(await submission)
            finally:
                raise
        self.active.add(operation)
        trace = {
            "role": role,
            "receipt_id": receipt_id,
            "operation_id": operation,
            "submitted_at": time.time(),
        }
        self.jobs.append(trace)
        log("child.submitted", **trace)
        deadline = time.monotonic() + timeout + 30
        try:
            while time.monotonic() < deadline:
                completed = await asyncio.to_thread(self.api.get_operation, operation)
                if completed.done:
                    self.active.discard(operation)
                    trace["finished_at"] = time.time()
                    trace["status"] = completed.status
                    result = completed.execution_result(require_image=True)
                    for output in (result.stdout, result.stderr):
                        if output:
                            print(output, end="" if output.endswith("\n") else "\n", flush=True)
                    image = result.image
                    trace["image"] = image
                    log("child.completed", **trace)
                    return image
                await asyncio.sleep(1)
            raise ExecutionFailed("Receipt sandbox exceeded its wait deadline")
        finally:
            if operation in self.active:
                await self.cancel(operation)

    async def process(self, sources, receipts, work):
        await self.prepare(sources)
        semaphore = asyncio.Semaphore(self.config["concurrency"])
        outcomes = {}

        async def worker(source):
            async with semaphore:
                key = source["receipt_id"]
                files = {
                    source["path"]: self.inputs[source["path"]],
                    "/app/inputs.json": await self.upload_json([source]),
                }
                try:
                    image = await self.job("receipt", files, key)
                except (OperationFailed, ExecutionFailed) as exc:
                    record = Receipt(
                        **{name: source[name] for name in ("receipt_id", "source", "credit")},
                        error=str(exc),
                    )
                else:
                    payload = json.loads(
                        await asyncio.to_thread(self.api.download, image, "/app/output/result.json")
                    )
                    if payload["status"] == "failed":
                        raise RuntimeError(
                            "Receipt worker reported a shared inference/configuration failure"
                        )
                    record = Receipt.model_validate(payload["receipt"])
                    if record.receipt_id != key or record.source != source["source"]:
                        raise RuntimeError("Receipt worker returned another input identity")
                    record.credit = source["credit"]
                    record.rendered_pages = []
                    trace = next(job for job in self.jobs if job.get("image") == image)
                    trace["worker_started_at"] = payload["started_at"]
                    trace["worker_finished_at"] = payload["finished_at"]
                outcomes[key] = record
                # Retain source ordering, even for partial results on a later shared failure.
                receipts[:] = [
                    outcomes[s["receipt_id"]] for s in sources if s["receipt_id"] in outcomes
                ]
                log("receipt.collected", receipt_id=key, error=record.error)

        tasks = [asyncio.create_task(worker(source)) for source in sources]
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def report(self, sources, receipts, directory):
        files = dict(self.inputs)
        files["/app/inputs.json"] = await self.upload_json(sources)
        files["/app/receipts.json"] = await self.upload_json([r.model_dump() for r in receipts])
        image = await self.job("report", files)
        directory.mkdir(parents=True, exist_ok=True)
        response = await asyncio.to_thread(retrieve_result, self.api, image, directory)
        if response["status"] == "failed":
            raise RuntimeError("Report worker failed")
        log("report.retrieved", image=image)
        return {name: directory / name for name in ("report.json", "report.pdf")}
