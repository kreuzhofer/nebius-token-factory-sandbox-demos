"""Deterministic lifecycle probe: publish evidence, then exceed the server deadline."""

import tarfile
import time
from pathlib import Path

workspace = Path("/workspace")
output = Path("/opt/coding-result")
output.mkdir(parents=True, exist_ok=True)
(workspace / "startup.txt").write_text("deadline-probe-started\n")
with tarfile.open(output / "workspace.tar.gz", "w:gz") as archive:
    archive.add(workspace, arcname="workspace")
print("deadline-probe-started", flush=True)
time.sleep(60)
