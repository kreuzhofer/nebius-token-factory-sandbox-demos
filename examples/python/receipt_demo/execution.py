"""Entrypoint shared by coordinator, receipt, and report sandbox jobs."""

import asyncio
import json
import os
import signal
import time
from pathlib import Path

from configuration import SandboxConfig
from nebius_sandbox import SandboxClient

from .artifacts import artifact_refs
from .configuration import InferenceConfig


async def run(root=Path("/app"), *, model_factory=None):
    from .agents import CoordinatorAgent, ReceiptAgent, ReportAgent, log
    from .documents import prepare
    from .inference import Models
    from .models import Receipt

    started_at = time.time()
    config = json.loads((root / "workflow.json").read_text())
    role = config.get("role", "coordinator")
    execution = None
    inference = InferenceConfig.from_env(os.environ)
    sandbox = SandboxConfig.from_env(os.environ) if role == "coordinator" else None
    # Entrypoint owns credential removal; model construction has no environment side effects.
    for name in ("NEBIUS_API_KEY", "CONTREE_TOKEN", "CONTREE_PROJECT", "CONTREE_BASE_URL"):
        os.environ.pop(name, None)
    if sandbox:
        from .orchestration import SandboxExecution

        client = SandboxClient(sandbox.token, sandbox.project, sandbox.base_url)
        execution = SandboxExecution(client, config, inference.to_env(), root)
    models = (model_factory or Models)(inference)
    output, work = root / "output", root / "work"
    output.mkdir(parents=True, exist_ok=True)
    log("configuration", role=role, agent_model=models.agent_name, vision_model=models.vision_name)
    try:
        if role == "coordinator":
            sources = json.loads((root / "inputs.json").read_text())
            return await CoordinatorAgent(models, execution=execution).run(sources, work, output)
        if role == "receipt":
            source = json.loads((root / "inputs.json").read_text())[0]
            receipt = await ReceiptAgent(models).run(source, work / "pages")
            # Original files travel separately; worker-local paths are not portable.
            receipt.rendered_pages = []
            response = {
                "status": "completed",
                "receipt": receipt.model_dump(),
                "started_at": started_at,
                "finished_at": time.time(),
            }
        elif role == "report":
            receipts = [
                Receipt.model_validate(item)
                for item in json.loads((root / "receipts.json").read_text())
            ]
            sources = {s["receipt_id"]: s for s in json.loads((root / "inputs.json").read_text())}
            for receipt in receipts:
                source = sources[receipt.receipt_id]
                try:
                    receipt.rendered_pages, _, _ = prepare(
                        source["path"], work / "pages" / receipt.receipt_id
                    )
                except Exception:
                    if not receipt.error:
                        raise  # A readable original becoming unavailable is a report failure.
                    receipt.rendered_pages = []
            artifacts = await ReportAgent(models).run(receipts, output)
            response = {"status": "completed", "artifacts": artifact_refs(artifacts)}
        else:
            raise ValueError("Unknown sandbox agent role")
    except Exception as exc:
        response = {"status": "failed", "error": f"{role} workflow failed ({type(exc).__name__})"}
        log("worker.error", role=role, error=response["error"])
    finally:
        await models.close()
    (output / "result.json").write_text(json.dumps(response, ensure_ascii=False, indent=2))
    return response


def main():
    async def managed():
        loop, task = asyncio.get_running_loop(), asyncio.current_task()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, task.cancel)
        return await run()

    asyncio.run(managed())
