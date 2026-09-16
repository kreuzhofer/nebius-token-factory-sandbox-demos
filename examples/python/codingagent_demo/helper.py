"""One task in one fresh sandbox, with locally persisted identity and results."""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from http_transport import TransportError

from .runtime import MODEL, OPENCODE_VERSION


@dataclass(frozen=True)
class AgentConfig:
    api_key: str = field(repr=False)
    model: str = MODEL
    base_url: str = "https://api.tokenfactory.nebius.com/v1"


def run_task(client, config, image, task, *, files=(), output, timeout=300):
    """Block for one unattended task; return outcome and paths to retrieved artifacts.

    The image must be built with build_runtime(). A lost connection returns an
    interrupted outcome with the known operation ID and never resubmits work.
    """
    if not task.strip() or not config.api_key or not config.model:
        raise ValueError("Task, inference key and model are required")
    maximum = client.limits().get("instance_max_timeout")
    if not isinstance(maximum, int) or not 60 <= timeout <= maximum:
        raise ValueError("Task timeout must be between 60 seconds and the reported account limit")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    record = {
        "operation_id": None,
        "image": None,
        "status": "preparing",
        "model": config.model,
        "opencode_version": OPENCODE_VERSION,
        "timeout": timeout,
        "answer": "",
        "archive": None,
        "logs": [],
        "error": None,
    }
    start = time.monotonic()

    def save():
        record["elapsed_seconds"] = round(time.monotonic() - start, 3)
        (output / "job.json").write_text(json.dumps(record, indent=2))

    try:
        uploads = {}
        for source in map(Path, files):
            if source.is_symlink() or not source.exists():
                raise ValueError(
                    "Inputs must be existing regular files or directories, not symlinks"
                )
            paths = sorted(source.rglob("*")) if source.is_dir() else [source]
            for path in paths:
                relative = path.relative_to(source.parent)
                if any(
                    p in {".git", ".venv", "__pycache__", "node_modules", ".env"}
                    for p in relative.parts
                ):
                    continue
                if path.is_symlink():
                    raise ValueError("Input trees must not contain symlinks")
                if not path.is_file():
                    continue
                destination = "/workspace/" + relative.as_posix()
                if destination in uploads:
                    raise ValueError("Input paths overlap inside the workspace")
                uploads[destination] = client.upload(path.read_bytes())
        request = {
            "task": task,
            "model": config.model,
            "base_url": config.base_url,
            "timeout": timeout,
            "opencode_version": OPENCODE_VERSION,
        }
        uploads["/opt/coding-request.json"] = client.upload(json.dumps(request).encode())
        uploads["/opt/coding-worker.py"] = client.upload(
            Path(__file__).with_name("worker.py").read_bytes()
        )
        operation_id = client.submit(
            image,
            command="/usr/local/bin/python3",
            args=["-u", "/opt/coding-worker.py"],
            cwd="/workspace",
            files=uploads,
            env={"NEBIUS_API_KEY": config.api_key},
            timeout=timeout,
            networking=True,
            disposable=False,
            max_layer_bytes=2 * 1024**3,
            output_limit=1024**2,
        )
        record.update(operation_id=operation_id, status="running")
        save()
        print(f"Task job: {operation_id}", flush=True)
        operation = client.wait(
            operation_id,
            timeout + 120,
            check=False,
            on_status=lambda status: print(f"Sandbox: {status}", flush=True),
        )
        record["image"] = operation.image
        if operation.status == "CANCELLED":
            record.update(status="cancelled", error="Sandbox operation was cancelled")
        elif operation.status != "SUCCESS":
            record.update(status="failed", error="Sandbox operation failed")
        else:
            execution = operation.execution_result(check=False)
            if execution.timed_out:
                record.update(status="timed_out", error="Sandbox execution deadline reached")
            elif not execution.successful:
                record.update(status="failed", error="Sandbox process failed")
            else:
                try:
                    payload = json.loads(
                        client.download(operation.require_image(), "/opt/coding-result/result.json")
                    )
                    if payload["status"] not in {"completed", "failed", "timed_out"}:
                        raise ValueError("Invalid worker status")
                    record.update(
                        status=payload["status"],
                        answer=payload.get("answer", ""),
                        error=payload.get("error"),
                    )
                except (TransportError, ValueError, KeyError, TypeError) as exc:
                    record.update(
                        status="failed",
                        error=f"Task result summary unavailable or invalid: {type(exc).__name__}",
                    )
        if operation.image:
            for name in ("workspace.tar.gz", "events.jsonl", "stderr.log"):
                try:
                    data = client.download(operation.image, "/opt/coding-result/" + name)
                except TransportError:
                    continue
                path = output / name
                path.write_bytes(data)
                if name == "workspace.tar.gz":
                    record["archive"] = str(path)
                else:
                    record["logs"].append(str(path))
        if record["status"] == "completed" and record["archive"] is None:
            record.update(
                status="failed", error="Agent completed but its workspace archive is unavailable"
            )
    except (TransportError, TimeoutError, KeyboardInterrupt) as exc:
        record.update(
            status="interrupted",
            error=f"Result unconfirmed: {type(exc).__name__}; do not resubmit automatically",
        )
    except Exception as exc:
        record.update(
            status="failed",
            error=f"Task preparation or result decoding failed: {type(exc).__name__}",
        )
    finally:
        save()
        (output / "result.json").write_text(json.dumps(record, indent=2))
    return record
