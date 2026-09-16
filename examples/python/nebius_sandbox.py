"""Nebius sandbox operations, independent of any demo or agent workflow.

Submission is never retried. A successful operation does not imply a successful
process: callers inspect execution_result() before consuming execution output.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
import warnings
from dataclasses import dataclass, field
from urllib.parse import quote, urlencode

from http_transport import HttpTransport


class OperationFailed(RuntimeError):
    """A known operation reached a failed or cancelled terminal state."""


class ExecutionFailed(RuntimeError):
    """An operation succeeded, but its sandbox process failed."""


@dataclass(frozen=True)
class ExecutionResult:
    stdout: str
    stderr: str
    image: str | None


def _decode(stream):
    if stream.get("truncated"):
        raise RuntimeError("Sandbox output was truncated")
    value = stream.get("value", "")
    return base64.b64decode(value).decode() if stream.get("encoding") == "base64" else value


@dataclass(frozen=True)
class Operation:
    id: str
    status: str
    image: str | None = None
    _result: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_response(cls, operation_id, payload):
        return cls(
            operation_id,
            payload["status"],
            payload.get("result_image_uuid") or (payload.get("result") or {}).get("image"),
            (payload.get("metadata") or {}).get("result") or {},
        )

    @property
    def done(self):
        return self.status in ("SUCCESS", "FAILED", "CANCELLED")

    def require_success(self):
        if self.status in ("FAILED", "CANCELLED"):
            raise OperationFailed(f"Operation {self.id}: {self.status}")
        if self.status != "SUCCESS":
            raise RuntimeError(f"Operation {self.id} is not complete")

    def execution_result(self):
        self.require_success()
        state = self._result.get("state") or {}
        if (
            state.get("timed_out")
            or state.get("signal", -1) not in (None, -1, 0)
            or state.get("exit_code") != 0
        ):
            raise ExecutionFailed(f"Sandbox process {self.id} failed")
        return ExecutionResult(
            _decode(self._result.get("stdout") or {}),
            _decode(self._result.get("stderr") or {}),
            self.image,
        )


class SandboxClient:
    def __init__(self, token, project=None, base_url=None):
        self._http = HttpTransport(
            base_url or "https://api.tokenfactory.nebius.com/sandboxes/v1", token, project
        )

    def list_images(self, *, limit=100, offset=0):
        return self._http.request("GET", "/images?" + urlencode({"limit": limit, "offset": offset}))

    def import_image(self, registry_url, *, timeout=300):
        operation = self._http.request(
            "POST", "/images/import", {"registry": {"url": registry_url}, "timeout": timeout}
        )
        return operation["uuid"]

    def upload(self, data, *, mode="0600"):
        result = json.loads(self._http.transfer("POST", "/files", data, "application/octet-stream"))
        if result["sha256"] != hashlib.sha256(data).hexdigest():
            raise RuntimeError("Uploaded file checksum mismatch")
        return {"uuid": result["uuid"], "mode": mode}

    def download(self, image, path):
        return self._http.transfer(
            "GET", f"/inspect/{quote(image, safe='')}/download?" + urlencode({"path": path})
        )

    def submit(
        self,
        image,
        *,
        command,
        args=(),
        stdin=None,
        cwd=None,
        files=None,
        env=None,
        timeout=300,
        disposable=False,
        networking=False,
        max_layer_bytes=268435456,
        output_limit=65536,
    ):
        """Submit a sandbox command once and return its operation ID immediately."""
        body = {
            "image": image,
            "command": command,
            "args": list(args),
            "files": files or {},
            "env": env or {},
            "preserve_env": False,
            "disposable": disposable,
            "networking": {"enabled": networking},
            "timeout": timeout,
            "resources_limits": {"max_layer_bytes": max_layer_bytes},
            "truncate_output_at": output_limit,
        }
        if stdin is not None:
            body["stdin"] = {"value": stdin, "encoding": "ascii", "close": True}
        if cwd is not None:
            body["cwd"] = cwd
        return self._http.request("POST", "/instances", body)["uuid"]

    def get_operation(self, operation_id):
        payload = self._http.request("GET", "/operations/" + quote(operation_id, safe=""))
        return Operation.from_response(operation_id, payload)

    def cancel(self, operation_id):
        self._http.request("DELETE", "/operations/" + quote(operation_id, safe=""))

    def wait(self, operation_id, seconds):
        """Poll to completion; deadlines/interrupts cancel, connection failures do not resubmit."""
        deadline = time.monotonic() + seconds
        try:
            while time.monotonic() < deadline:
                operation = self.get_operation(operation_id)
                if operation.done:
                    operation.require_success()
                    return operation
                time.sleep(1)
            raise TimeoutError(f"Operation {operation_id} exceeded local deadline")
        except (KeyboardInterrupt, TimeoutError):
            try:
                self.cancel(operation_id)
            except Exception:
                warnings.warn(
                    f"Cancellation unconfirmed: {operation_id}; server timeout remains active",
                    RuntimeWarning,
                    stacklevel=2,
                )
            raise
