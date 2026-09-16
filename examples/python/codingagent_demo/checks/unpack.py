"""Unpack returned files and execute independent checks inside a validation sandbox."""

import subprocess
import sys
import tarfile

with tarfile.open("/checks/workspace.tar.gz", "r:gz") as archive:
    archive.extractall("/work", filter="data")
raise SystemExit(
    subprocess.call(
        [
            sys.executable,
            "/checks/validate.py",
            sys.argv[1],
            "/work/workspace",
        ]
    )
)
