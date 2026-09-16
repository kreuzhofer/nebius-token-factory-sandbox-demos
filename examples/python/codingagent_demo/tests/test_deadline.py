"""Observe confirmed deadlines and best-effort recovery at the public demo boundary."""

import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from http_transport import TransportError
from nebius_sandbox import Operation

from codingagent_demo.deadline import run_deadline_probe
from codingagent_demo.tests.test_run import TaskService


class DeadlineService(TaskService):
    def __init__(self, image=True):
        super().__init__()
        self.image = image

    def wait(self, operation, seconds, **options):
        return Operation.from_response(
            operation,
            {
                "status": "SUCCESS",
                "result_image_uuid": "checkpoint" if self.image else None,
                "metadata": {
                    "result": {
                        "state": {"exit_code": -1, "timed_out": True},
                        "stdout": {"value": "deadline-probe-started\n"},
                    }
                },
            },
        )

    def download(self, image, path):
        if path.endswith("workspace.tar.gz"):
            data = io.BytesIO()
            with tarfile.open(fileobj=data, mode="w:gz") as archive:
                marker = b"deadline-probe-started\n"
                member = tarfile.TarInfo("workspace/startup.txt")
                member.size = len(marker)
                archive.addfile(member, io.BytesIO(marker))
            return data.getvalue()
        raise TransportError("GET request failed: HTTP 404")


class DeadlineTests(unittest.TestCase):
    def test_confirmed_deadline_retains_identity_and_reports_artifact_availability(self):
        for image in (True, False):
            with self.subTest(image=image), tempfile.TemporaryDirectory() as directory:
                api = DeadlineService(image)
                result = run_deadline_probe(api, "runtime", Path(directory) / "probe")
                self.assertTrue(result["passed"])
                self.assertEqual(result["task"]["status"], "timed_out")
                self.assertEqual(result["task"]["operation_id"], "task-job")
                self.assertEqual(
                    result["archive_recovery"], "recovered" if image else "unavailable"
                )
                self.assertEqual(len(api.submissions), 1)
                options = api.submissions[0][1]
                self.assertEqual(options["timeout"], 15)
                self.assertFalse(options["networking"])
                self.assertFalse(options.get("env"))
                saved = json.loads((Path(directory) / "probe/deadline.json").read_text())
                self.assertEqual(saved["task"]["operation_id"], "task-job")
