"""Observe automatic progression and independent-check failures through the example API."""

import json
import tempfile
import unittest
from pathlib import Path

from http_transport import TransportError
from nebius_sandbox import Operation

from codingagent_demo import AgentConfig
from codingagent_demo.examples import run_example, run_ladder
from codingagent_demo.tests.test_run import TaskService


class ValidationService(TaskService):
    def submit(self, image, **options):
        super().submit(image, **options)
        return "task-job" if len(self.submissions) == 1 else "validation-job"

    def wait(self, operation, seconds, **options):
        if operation == "task-job":
            return super().wait(operation, seconds, **options)
        return Operation.from_response(
            operation,
            {
                "status": "SUCCESS",
                "metadata": {"result": {"state": {"exit_code": 1}}},
            },
        )


class LadderTests(unittest.TestCase):
    def test_failed_checks_preserve_completed_task_and_stop_progression(self):
        api = ValidationService()
        with tempfile.TemporaryDirectory() as directory:
            result = run_ladder(api, AgentConfig("secret"), "runtime", Path(directory) / "ladder")
            self.assertFalse(result["passed"])
            self.assertEqual(len(result["runs"]), 1)
            self.assertEqual(result["runs"][0]["task"]["status"], "completed")
            self.assertFalse(result["runs"][0]["validation"]["passed"])
            self.assertEqual(len(api.submissions), 2)
            validation = api.submissions[1][1]
            self.assertFalse(validation["networking"])
            self.assertFalse(validation.get("env"))
            self.assertEqual(validation["timeout"], 60)

    def test_validation_connection_loss_preserves_operation_id_without_retry(self):
        class DisconnectedValidation(ValidationService):
            def wait(self, operation, seconds, **options):
                if operation == "validation-job":
                    saved = json.loads((output / "example.json").read_text())
                    self.saved_id = saved["validation"]["operation_id"]
                    raise TransportError("GET request failed: connection unavailable")
                return super().wait(operation, seconds, **options)

        api = DisconnectedValidation()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "example"
            result = run_example(api, AgentConfig("secret"), "runtime", "create", output)
            self.assertEqual(api.saved_id, "validation-job")
            self.assertEqual(result["validation"]["operation_id"], "validation-job")
            self.assertFalse(result["passed"])
            self.assertEqual(len(api.submissions), 2)
