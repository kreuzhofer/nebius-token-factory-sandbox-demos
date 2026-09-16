"""Exercise the sandbox wire contract and distinguish transport, operation, and process failure."""

import json
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from http_transport import TransportError
from nebius_sandbox import ExecutionFailed, Operation, OperationFailed, SandboxClient


class SandboxClientTests(unittest.TestCase):
    def setUp(self):
        self.client = SandboxClient("secret", "project", "https://sandbox.example/v1/")

    def test_submit_maps_generic_command_without_receipt_defaults(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"uuid":"job"}'
        with patch("http_transport.urllib.request.urlopen", return_value=response) as send:
            operation = self.client.submit(
                "image",
                command="/bin/sh",
                args=["-c", "echo ready"],
                cwd="/work",
                files={"/work/input": {"uuid": "file", "mode": "0400"}},
                env={"EXAMPLE": "value"},
                timeout=12,
            )
        request = send.call_args.args[0]
        self.assertEqual(operation, "job")
        self.assertEqual(request.full_url, "https://sandbox.example/v1/instances")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertEqual(request.get_header("Project"), "project")
        body = json.loads(request.data)
        self.assertEqual(body["command"], "/bin/sh")
        self.assertEqual(body["args"], ["-c", "echo ready"])
        self.assertEqual(body["cwd"], "/work")
        self.assertEqual(body["files"]["/work/input"]["uuid"], "file")
        self.assertEqual(body["env"], {"EXAMPLE": "value"})
        self.assertEqual(body["timeout"], 12)
        self.assertFalse(body["preserve_env"])
        self.assertFalse(body["networking"]["enabled"])
        self.assertNotIn("stdin", body)

    def test_ambiguous_submission_is_not_retried_or_leaked(self):
        with patch("http_transport.urllib.request.urlopen", side_effect=URLError("secret")) as send:
            with self.assertRaises(TransportError) as raised:
                self.client.submit("image", command="/bin/true")
        self.assertEqual(send.call_count, 1)
        self.assertNotIn("secret", str(raised.exception))

    def test_http_error_body_is_not_exposed(self):
        error = HTTPError("https://sandbox.example", 401, "secret", {}, BytesIO(b"secret"))
        with patch("http_transport.urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(TransportError, "HTTP 401") as raised:
                self.client.list_images()
        self.assertNotIn("secret", str(raised.exception))

    def test_image_import_listing_and_fallback_result(self):
        with patch.object(self.client._http, "request", return_value={"uuid": "import"}) as send:
            self.assertEqual(
                self.client.import_image("docker://example/image", timeout=15), "import"
            )
            send.assert_called_once_with(
                "POST",
                "/images/import",
                {
                    "registry": {"url": "docker://example/image"},
                    "timeout": 15,
                },
            )
        with patch.object(self.client._http, "request", return_value={"images": []}) as send:
            self.assertEqual(self.client.list_images(limit=2, offset=3), {"images": []})
            send.assert_called_once_with("GET", "/images?limit=2&offset=3")
        with patch.object(
            self.client._http,
            "request",
            return_value={
                "status": "SUCCESS",
                "result": {"image": "imported"},
            },
        ):
            self.assertEqual(self.client.wait("import", 5).image, "imported")

    def test_poll_until_success(self):
        with (
            patch.object(
                self.client._http,
                "request",
                side_effect=[
                    {"status": "EXECUTING"},
                    {"status": "SUCCESS"},
                ],
            ),
            patch("nebius_sandbox.time.sleep"),
        ):
            self.assertEqual(self.client.wait("id", 5).status, "SUCCESS")

    def test_import_completion_requires_a_successful_retained_image(self):
        for final, expected, error in (
            ({"status": "SUCCESS", "result": {"image": "ready"}}, "ready", None),
            ({"status": "SUCCESS"}, None, RuntimeError),
            ({"status": "FAILED", "result_image_uuid": "partial"}, None, OperationFailed),
        ):
            with (
                self.subTest(final=final),
                patch.object(
                    self.client._http,
                    "request",
                    side_effect=[{"uuid": "import-job"}, {"status": "PENDING"}, final],
                ) as send,
                patch("nebius_sandbox.time.sleep"),
            ):
                if error:
                    with self.assertRaises(error):
                        self.client.import_image_and_wait("docker://example/runtime", timeout=20)
                else:
                    self.assertEqual(
                        self.client.import_image_and_wait("docker://example/runtime", timeout=20),
                        expected,
                    )
                self.assertEqual(send.call_args_list[0].args[2]["timeout"], 20)
                self.assertEqual(send.call_args_list[-1].args, ("GET", "/operations/import-job"))

    def test_import_wait_deadline_cancels_known_import(self):
        with patch.object(
            self.client._http, "request", return_value={"uuid": "import-job"}
        ) as send:
            with self.assertRaises(TimeoutError):
                self.client.import_image_and_wait("docker://example/runtime", wait_timeout=-1)
            self.assertEqual(send.call_args.args, ("DELETE", "/operations/import-job"))

    def test_deadline_cancels(self):
        with patch.object(self.client._http, "request") as send:
            with self.assertRaises(TimeoutError):
                self.client.wait("id", -1)
            send.assert_called_once_with("DELETE", "/operations/id")

    def test_interruption_cancels_but_transport_failure_leaves_known_job(self):
        for error in (KeyboardInterrupt(), TransportError("unavailable")):
            with (
                self.subTest(error=type(error).__name__),
                patch.object(self.client, "get_operation", side_effect=error),
                patch.object(self.client, "cancel") as cancel,
                self.assertRaises(type(error)),
            ):
                try:
                    self.client.wait("id", 5)
                finally:
                    self.assertEqual(cancel.call_count, int(isinstance(error, KeyboardInterrupt)))

    def test_failed_operation_differs_from_failed_process(self):
        for status in ("FAILED", "CANCELLED"):
            with (
                self.subTest(status=status),
                patch.object(self.client._http, "request", return_value={"status": status}),
            ):
                with self.assertRaises(OperationFailed):
                    self.client.wait("job", 5)
        for state in (
            {"exit_code": 1},
            {"exit_code": 0, "timed_out": True},
            {"exit_code": 0, "signal": 9},
            {},
        ):
            operation = Operation.from_response(
                "job", {"status": "SUCCESS", "metadata": {"result": {"state": state}}}
            )
            with self.subTest(state=state), self.assertRaises(ExecutionFailed):
                operation.execution_result()

    def test_execution_decodes_streams_and_rejects_truncation(self):
        payload = {
            "status": "SUCCESS",
            "result_image_uuid": "retained",
            "metadata": {
                "result": {
                    "state": {"exit_code": 0},
                    "stdout": {"encoding": "base64", "value": "aGVsbG8="},
                    "stderr": {"value": "notice"},
                }
            },
        }
        result = Operation.from_response("job", payload).execution_result()
        self.assertEqual(
            (result.stdout, result.stderr, result.image), ("hello", "notice", "retained")
        )
        payload["metadata"]["result"]["stdout"]["truncated"] = True
        with self.assertRaisesRegex(RuntimeError, "truncated"):
            Operation.from_response("job", payload).execution_result()

    def test_artifact_execution_requires_image_but_disposable_execution_does_not(self):
        payload = {"status": "SUCCESS", "metadata": {"result": {"state": {"exit_code": 0}}}}
        operation = Operation.from_response("job", payload)
        self.assertIsNone(operation.execution_result().image)
        with self.assertRaisesRegex(RuntimeError, "job.*no filesystem image"):
            operation.execution_result(require_image=True)
        payload["result_image_uuid"] = "retained"
        self.assertEqual(
            Operation.from_response("job", payload).execution_result(require_image=True).image,
            "retained",
        )
        payload["metadata"]["result"]["state"]["exit_code"] = 1
        with self.assertRaises(ExecutionFailed):
            Operation.from_response("job", payload).execution_result(require_image=True)

    def test_upload_rejects_checksum_mismatch(self):
        with patch.object(
            self.client._http, "transfer", return_value=b'{"uuid":"file","sha256":"wrong"}'
        ):
            with self.assertRaisesRegex(RuntimeError, "checksum"):
                self.client.upload(b"contents")
