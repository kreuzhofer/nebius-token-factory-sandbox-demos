"""Confirm server timeout handling without inference or automatic resubmission."""

import json
import tarfile
from pathlib import Path

from .job import run_workspace_job


def run_deadline_probe(client, image, output):
    """Run a 60-second command with a 15-second cap and report recoverable evidence."""
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    record = {
        "stage": "deadline",
        "passed": False,
        "task": None,
        "archive_recovery": "unavailable",
        "error": None,
    }
    try:
        script = Path(__file__).with_name("deadline_worker.py")
        record["task"] = run_workspace_job(
            client,
            image,
            output=output / "task",
            timeout=15,
            files={"/opt/deadline-probe.py": client.upload(script.read_bytes())},
            script="/opt/deadline-probe.py",
        )
        task = record["task"]
        record["passed"] = task["status"] == "timed_out"
        if task["archive"]:
            record["archive_recovery"] = "invalid"
            with tarfile.open(task["archive"], "r:gz") as archive:
                with archive.extractfile("workspace/startup.txt") as marker:
                    if marker.read() != b"deadline-probe-started\n":
                        raise ValueError("Unexpected startup marker")
            record["archive_recovery"] = "recovered"
    except Exception as exc:
        record.update(passed=False, error=f"Deadline probe failed: {type(exc).__name__}")
    finally:
        (output / "deadline.json").write_text(json.dumps(record, indent=2))
    return record
