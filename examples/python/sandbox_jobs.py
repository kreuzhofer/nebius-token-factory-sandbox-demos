"""Small job/file helpers shared by receipt launchers and sandbox coordinators."""

import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

from demo import API, decode


class SandboxJobs(API):
    def upload(self, data):
        result = json.loads(self.transfer("POST", "/files", data, "application/octet-stream"))
        if result["sha256"] != hashlib.sha256(data).hexdigest():
            raise RuntimeError("Uploaded file checksum mismatch")
        return {"uuid": result["uuid"], "mode": "0600"}

    def download(self, image, path):
        return self.transfer("GET", f"/inspect/{image}/download?" + urlencode({"path": path}))

    def python_image(self, image=None):
        if image:
            return image
        operation = self.request(
            "POST",
            "/images/import",
            {"registry": {"url": "docker://docker.io/library/python:3.12-slim"}, "timeout": 300},
        )
        print(f"Image import operation: {operation['uuid']}", flush=True)
        result = self.wait(operation["uuid"], 360)
        image = result.get("result_image_uuid") or (result.get("result") or {}).get("image")
        if not image:
            raise RuntimeError("Image import returned no image")
        print(f"Reuse base image with --image {image}", flush=True)
        return image

    def submit(self, image, files, script, env, timeout):
        """Submit once; callers own polling and cancellation after obtaining the ID."""
        operation = self.request(
            "POST",
            "/instances",
            {
                "image": image,
                "command": "/usr/local/bin/python3",
                "args": ["-u", "-"],
                "stdin": {"value": script, "encoding": "ascii", "close": True},
                "cwd": "/app",
                "files": files,
                "env": env,
                "preserve_env": False,
                "disposable": False,
                "networking": {"enabled": True},
                "timeout": timeout,
                "resources_limits": {"max_layer_bytes": 1073741824},
                "truncate_output_at": 1048576,
            },
        )
        return operation["uuid"]

    def run(self, image, files, script, env, timeout):
        operation_id = self.submit(image, files, script, env, timeout)
        print(f"Coordinator job: {operation_id}", flush=True)
        completed = self.wait(operation_id, timeout + 120)
        return operation_id, self.result_image(operation_id, completed)

    def result_image(self, operation_id, completed):
        result = completed["metadata"]["result"]
        for stream in ("stdout", "stderr"):
            output = decode(result.get(stream) or {})
            if output:
                print(output, end="" if output.endswith("\n") else "\n", flush=True)
        state = result["state"]
        if (
            state.get("timed_out")
            or state.get("signal", -1) not in (None, -1, 0)
            or state.get("exit_code") != 0
        ):
            raise ChildJobError(f"Job {operation_id} failed: {state}")
        result_image = completed.get("result_image_uuid")
        if not result_image:
            raise RuntimeError(f"Coordinator job {operation_id} returned no filesystem image")
        return result_image


class ChildJobError(RuntimeError):
    """A known job terminated unsuccessfully; distinct from shared API failures."""


def retrieve_result(api, image, output):
    """Only retrieve coordinator-owned outputs; leave failed transfers retryable."""
    output = Path(output)
    response = json.loads(api.download(image, "/app/output/result.json"))
    if response["status"] != "failed":
        for name in ("report.json", "report.pdf"):
            ref = response["artifacts"][name]
            if ref["path"] != "/app/output/" + name:
                raise RuntimeError("Unexpected coordinator artifact path")
            data = api.download(image, ref["path"])
            if len(data) != ref["bytes"] or hashlib.sha256(data).hexdigest() != ref["sha256"]:
                raise RuntimeError(f"Artifact checksum mismatch: {name}")
            if name.endswith(".pdf") and not data.startswith(b"%PDF-"):
                raise RuntimeError("Coordinator returned an invalid PDF")
            (output / (name + ".part")).write_bytes(data)
        for name in ("report.json", "report.pdf"):
            (output / (name + ".part")).replace(output / name)
    (output / "result.json").write_text(json.dumps(response, ensure_ascii=False, indent=2))
    return response
