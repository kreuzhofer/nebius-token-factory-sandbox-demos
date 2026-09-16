import contextlib
import io
import unittest
from unittest.mock import patch

import demo


class LifecycleTests(unittest.TestCase):
    def test_poll_until_success(self):
        api = demo.API("test", "project")
        with (
            patch.object(
                api, "request", side_effect=[{"status": "EXECUTING"}, {"status": "SUCCESS"}]
            ),
            patch("demo.time.sleep"),
        ):
            self.assertEqual(api.wait("id", 5)["status"], "SUCCESS")

    def test_deadline_cancels(self):
        api = demo.API("test", "project")
        with patch.object(api, "request") as request:
            with self.assertRaises(TimeoutError):
                api.wait("id", -1)
            request.assert_called_once_with("DELETE", "/operations/id")

    def test_process_failure_even_when_operation_succeeds(self):
        api = demo.API("test", "project")
        with (
            patch.object(api, "request", return_value={"uuid": "id"}),
            patch.object(
                api, "wait", return_value={"metadata": {"result": {"state": {"exit_code": 1}}}}
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            with self.assertRaises(RuntimeError):
                demo.execute(api, "image", "smoke", {})

    def test_agent_request_is_disposable(self):
        api = demo.API("test", "project")
        with (
            patch.object(api, "request", return_value={"uuid": "id"}) as request,
            patch.object(
                api,
                "wait",
                return_value={"metadata": {"result": {"state": {"exit_code": 0, "signal": -1}}}},
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            demo.execute(api, "image", "agent", {"NEBIUS_API_KEY": "test"})
            body = request.call_args.args[2]
            self.assertTrue(body["disposable"])
            self.assertFalse(body["preserve_env"])
            self.assertTrue(body["networking"]["enabled"])
            self.assertNotIn("test", body["stdin"]["value"])

    def test_decodes_base64(self):
        self.assertEqual(demo.decode({"encoding": "base64", "value": "aGVsbG8="}), "hello")


if __name__ == "__main__":
    unittest.main()
