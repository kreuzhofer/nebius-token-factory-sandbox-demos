"""Small launchers use the same sandbox client without owning its wire format."""

import contextlib
import io
import unittest
from unittest.mock import patch

from nebius_sandbox import ExecutionFailed, Operation, SandboxClient

from basic_demo import __main__ as demo


class DemoTests(unittest.TestCase):
    def test_process_failure_even_when_operation_succeeds(self):
        client = SandboxClient("test", "project")
        operation = Operation.from_response(
            "id",
            {
                "status": "SUCCESS",
                "metadata": {"result": {"state": {"exit_code": 1}}},
            },
        )
        with (
            patch.object(client, "submit", return_value="id"),
            patch.object(client, "wait", return_value=operation),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            with self.assertRaises(ExecutionFailed):
                demo.execute(client, "image", "smoke", {})

    def test_agent_request_is_disposable(self):
        client = SandboxClient("test", "project")
        operation = Operation.from_response(
            "id",
            {
                "status": "SUCCESS",
                "metadata": {"result": {"state": {"exit_code": 0}}},
            },
        )
        with (
            patch.object(client, "submit", return_value="id") as submit,
            patch.object(client, "wait", return_value=operation),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            demo.execute(client, "image", "agent", {"NEBIUS_API_KEY": "test"})
            options = submit.call_args.kwargs
            self.assertTrue(options["disposable"])
            self.assertTrue(options["networking"])
            self.assertEqual(options["env"], {"NEBIUS_API_KEY": "test"})
            self.assertNotIn("test", options["stdin"])
