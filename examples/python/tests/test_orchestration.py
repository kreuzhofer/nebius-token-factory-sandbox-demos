"""Exercise the coordinator's real fan-out/transfer code against a fake sandbox API."""

import asyncio
import hashlib
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel
from receipt_demo.agents import CoordinatorAgent
from receipt_demo.models import Decisions, Receipt
from receipt_demo.orchestration import SandboxExecution
from receipt_demo.reconcile import reconcile
from sandbox_jobs import SandboxJobs

from tests.test_receipts import tool_model

ROOT = Path(__file__).resolve().parent.parent


class FakeSandbox(SandboxJobs):
    def __init__(self, fail=None, corrupt=False):
        self.blobs, self.operations, self.outputs = {}, {}, {}
        self.fail, self.corrupt = fail, corrupt
        self.lock = threading.Lock()
        self.active, self.peak = 0, 0
        self.cancelled, self.finished = [], []
        self.submissions = []

    def upload(self, data):
        key = hashlib.sha256(data).hexdigest()
        self.blobs[key] = data
        return {"uuid": key, "mode": "0600"}

    def unpack(self, files, path):
        return json.loads(self.blobs[files[path]["uuid"]])

    def submit(self, image, files, script, env, timeout):
        role = self.unpack(files, "/app/workflow.json")["role"]
        sources = self.unpack(files, "/app/inputs.json")
        key = sources[0]["receipt_id"] if role == "receipt" else "report"
        with self.lock:
            operation = "job-" + str(len(self.operations) + 1)
            self.operations[operation] = {"key": key, "polls": 0, "finished": False}
            self.active += 1
            self.peak = max(self.active, self.peak)
            self.submissions.append((role, files, env))
        if role == "receipt":
            source = sources[0]
            record = Receipt(
                receipt_id=key,
                source=source["source"],
                credit=source["credit"],
                total="10.00",
                currency="EUR",
                transaction_type="purchase",
            )
            result = {
                "status": "completed",
                "receipt": record.model_dump(),
                "started_at": time.time(),
                "finished_at": time.time() + 1,
            }
            if self.fail == "shared-" + key:
                result = {"status": "failed", "error": "Inference configuration failed"}
            self.outputs[operation] = {"result.json": json.dumps(result).encode()}
        else:
            records = [Receipt.model_validate(r) for r in self.unpack(files, "/app/receipts.json")]
            report = reconcile(records, Decisions())
            data = {"report.json": report.model_dump_json().encode(), "report.pdf": b"%PDF-fake"}
            refs = {
                name: {
                    "path": "/app/output/" + name,
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
                for name, raw in data.items()
            }
            if self.corrupt:
                refs["report.pdf"]["sha256"] = "bad"
            data["result.json"] = json.dumps({"status": "completed", "artifacts": refs}).encode()
            self.outputs[operation] = data
        return operation

    def request(self, method, path, body=None):
        operation = path.rsplit("/", 1)[-1]
        with self.lock:
            info = self.operations[operation]
            if method == "DELETE":
                self.cancelled.append(operation)
                if not info["finished"]:
                    self.active -= 1
                    info["finished"] = True
                return {}
            info["polls"] += 1
            # First input finishes last; other workers must continue in the meantime.
            if info["key"] == "a" and info["polls"] < 3:
                return {"status": "EXECUTING"}
            if not info["finished"]:
                self.active -= 1
                info["finished"] = True
                self.finished.append(info["key"])
        state = {"exit_code": 0}
        if self.fail == info["key"]:
            state = {"exit_code": 1, "timed_out": True}
        return {
            "status": "SUCCESS",
            "result_image_uuid": operation,
            "metadata": {"result": {"state": state}},
        }

    def download(self, image, path):
        return self.outputs[image][Path(path).name]


class OrchestrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_coordinator_cannot_succeed_without_executing_tool(self):
        models = SimpleNamespace(
            agent=FunctionModel(lambda messages, info: ModelResponse(parts=[TextPart("Done")]))
        )
        with tempfile.TemporaryDirectory() as directory:
            result = await CoordinatorAgent(models, self.execution(FakeSandbox())).run(
                [], Path(directory), Path(directory) / "output"
            )
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["artifacts"], {})
            self.assertEqual(result["jobs"], [])

    async def test_default_launcher_starts_only_coordinator_with_orchestration_config(self):
        import receipts

        api = FakeSandbox()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                "os.environ",
                {
                    "NEBIUS_API_KEY": "inference-key",
                    "CONTREE_TOKEN": "sandbox-key",
                    "CONTREE_PROJECT": "project",
                },
                clear=True,
            ),
        ):
            with (
                patch("sys.argv", ["receipts.py", "--profile", "minimal", "--output", directory]),
                patch("receipts.load_env"),
                patch("receipts.SandboxJobs", return_value=api),
                patch.object(api, "python_image", return_value="base"),
                patch.object(api, "run", return_value=("parent", "parent-image")) as run,
                patch("receipts.retrieve_result", return_value={"status": "completed"}),
            ):
                receipts.main()
            run.assert_called_once()
            image, files, script, env, timeout = run.call_args.args
            config = api.unpack(files, "/app/workflow.json")
            self.assertEqual(config["role"], "coordinator")
            self.assertEqual(config["concurrency"], 3)
            self.assertNotIn("mode", config)
            self.assertIn("/app/sandbox_jobs.py", files)
            self.assertEqual(env["CONTREE_TOKEN"], "sandbox-key")
            self.assertEqual(env["NEBIUS_API_KEY"], "inference-key")

    def execution(self, api):
        return SandboxExecution(
            api,
            {"image": "base", "concurrency": 2, "child_timeout": 300},
            {"NEBIUS_API_KEY": "inference-only"},
            ROOT,
        )

    async def run_batch(self, api, directory):
        sources = [
            {
                "receipt_id": key,
                "source": key + ".txt",
                "path": str(ROOT / "README.md"),
                "credit": "source credit",
            }
            for key in ("a", "b", "c")
        ]
        execution = self.execution(api)
        models = SimpleNamespace(agent=FunctionModel(tool_model))
        coordinator = CoordinatorAgent(models, execution)
        result = await coordinator.run(
            sources, Path(directory) / "work", Path(directory) / "output"
        )
        return result, execution

    async def test_fanout_bound_order_originals_and_coordinator_artifacts(self):
        api = FakeSandbox()
        with tempfile.TemporaryDirectory() as directory:
            result, execution = await self.run_batch(api, directory)
            self.assertEqual(result["status"], "completed")
            self.assertEqual([e["receipt_id"] for e in result["entries"]], ["a", "b", "c"])
            self.assertEqual(api.peak, 2)
            self.assertEqual(api.finished, ["b", "c", "a", "report"])
            self.assertEqual(len(result["jobs"]), 4)
            self.assertEqual(result["totals"], {"EUR": "30.00"})
            self.assertEqual((Path(directory) / "output/report.pdf").read_bytes(), b"%PDF-fake")
            role, files, env = api.submissions[-1]
            self.assertEqual(role, "report")
            self.assertIn(
                str(ROOT / "README.md"), files
            )  # Original evidence travels to report job.
            for _, _, env in api.submissions:
                self.assertNotIn("CONTREE_TOKEN", env)
                self.assertEqual(env["NEBIUS_API_KEY"], "inference-only")
            self.assertFalse(execution.active)

    async def test_child_timeout_is_contained_and_report_still_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            result, _ = await self.run_batch(FakeSandbox(fail="b"), directory)
            self.assertEqual(
                [e["outcome"] for e in result["entries"]], ["included", "error", "included"]
            )
            self.assertEqual(result["status"], "completed_with_flags")
            self.assertEqual(result["totals"], {"EUR": "20.00"})

    async def test_report_failure_and_bad_download_preserve_known_outcomes(self):
        for api in (FakeSandbox(fail="report"), FakeSandbox(corrupt=True)):
            with self.subTest(api=api), tempfile.TemporaryDirectory() as directory:
                result, _ = await self.run_batch(api, directory)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(len(result["entries"]), 3)
                self.assertEqual(result["artifacts"], {})
                self.assertFalse((Path(directory) / "output/report.pdf").exists())

    async def test_shared_failure_cancels_other_children(self):
        api = FakeSandbox(fail="shared-b")
        with tempfile.TemporaryDirectory() as directory:
            result, execution = await self.run_batch(api, directory)
            self.assertEqual(result["status"], "failed")
            self.assertIn("job-1", api.cancelled)
            self.assertFalse(execution.active)
            self.assertNotIn("report", [role for role, _, _ in api.submissions])

    async def test_cancellation_during_submission_cleans_up_returned_id(self):
        api = FakeSandbox()
        execution = self.execution(api)
        execution.code = {}
        started, finish = threading.Event(), threading.Event()

        def submit(*args):
            started.set()
            finish.wait(2)
            return "late-job"

        with (
            patch.object(api, "submit", side_effect=submit),
            patch.object(api, "request") as request,
        ):
            task = asyncio.create_task(execution.job("receipt", {}))
            await asyncio.to_thread(started.wait, 2)
            task.cancel()
            finish.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
            await execution.close()
            request.assert_called_once_with("DELETE", "/operations/late-job")

    async def test_ambiguous_submission_is_never_retried(self):
        api = FakeSandbox()
        execution = self.execution(api)
        execution.code = {}
        with patch.object(api, "submit", side_effect=TimeoutError("Ambiguous POST")) as submit:
            with self.assertRaises(TimeoutError):
                await execution.job("receipt", {})
            self.assertEqual(submit.call_count, 1)

    async def test_wait_deadline_requests_child_cancellation(self):
        api = FakeSandbox()
        execution = self.execution(api)
        execution.code = {}
        clock = SimpleNamespace(monotonic=Mock(side_effect=[0, 331]), time=time.time)
        with (
            patch.object(api, "submit", return_value="slow-job"),
            patch.object(api, "request") as request,
        ):
            with patch("receipt_demo.orchestration.time", clock):
                from sandbox_jobs import ChildJobError

                with self.assertRaises(ChildJobError):
                    await execution.job("receipt", {})
            request.assert_called_once_with("DELETE", "/operations/slow-job")
            self.assertFalse(execution.active)

    async def test_parent_cancellation_returns_failure_and_cleans_up(self):
        api = FakeSandbox()
        with tempfile.TemporaryDirectory() as directory:
            task = asyncio.create_task(self.run_batch(api, directory))
            for _ in range(100):
                if api.operations:
                    break
                await asyncio.sleep(0.01)
            self.assertTrue(api.operations)
            task.cancel()
            result, execution = await task
            self.assertEqual(result["status"], "failed")
            self.assertFalse(execution.active)
            self.assertTrue(api.cancelled)


if __name__ == "__main__":
    unittest.main()
