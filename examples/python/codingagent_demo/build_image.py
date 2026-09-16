"""Runs inside the image-build sandbox, without inference or sandbox API credentials."""

import base64
import hashlib
import io
import json
import os
import subprocess
import tarfile
import urllib.request
from pathlib import Path

VERSION = "1.18.31"
PACKAGE = "opencode-linux-x64-baseline"
INTEGRITY = (
    "T/hyCHb7gSCuJzLDXs8YfEhjelUes2zkWFPTGEdBPqV/eKrKbEo9U1YdA/WvntjXv0I6k+blZEID54QIcF7Djw=="
)


def main():
    subprocess.run(["apt-get", "update", "-qq"], check=True, timeout=90)
    subprocess.run(
        ["apt-get", "install", "-y", "-qq", "--no-install-recommends", "git", "ripgrep"],
        check=True,
        timeout=120,
    )
    url = f"https://registry.npmjs.org/{PACKAGE}/-/{PACKAGE}-{VERSION}.tgz"
    with urllib.request.urlopen(url, timeout=60) as response:
        raw = response.read()
    if base64.b64encode(hashlib.sha512(raw).digest()).decode() != INTEGRITY:
        raise RuntimeError("OpenCode archive integrity mismatch")
    binary = Path("/usr/local/bin/opencode")
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        with archive.extractfile("package/bin/opencode") as source:
            binary.write_bytes(source.read())
    binary.chmod(0o755)
    actual = subprocess.check_output([str(binary), "--version"], text=True).strip()
    if actual != VERSION:
        raise RuntimeError("Unexpected OpenCode version")
    Path("/workspace").mkdir(exist_ok=True)
    # Populate runtime caches without provider credentials or a model call.
    env = dict(
        os.environ, OPENCODE_DISABLE_AUTOUPDATE="true", OPENCODE_DISABLE_DEFAULT_PLUGINS="true"
    )
    subprocess.run(
        [str(binary), "models"], env=env, check=True, timeout=60, stdout=subprocess.DEVNULL
    )
    Path("/opt/coding-runtime.json").write_text(json.dumps({"opencode_version": actual}))
    print(json.dumps({"opencode_version": actual, "runtime_ready": True}), flush=True)


if __name__ == "__main__":
    main()
