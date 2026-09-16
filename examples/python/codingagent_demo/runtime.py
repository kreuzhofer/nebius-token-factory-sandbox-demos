"""Build a credential-free OpenCode image once; task jobs reuse its filesystem."""

import json
from pathlib import Path

from .build_image import VERSION as OPENCODE_VERSION

MODEL = "moonshotai/Kimi-K2.7-Code"


def build_runtime(client, output, *, base_image=None):
    """Return a reusable image and record its identity before and after the build."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / "runtime.json"
    if manifest.exists():
        raise FileExistsError("Use a fresh runtime output directory")
    base_image = base_image or client.import_image_and_wait(
        "docker://docker.io/library/python:3.12-slim"
    )
    operation_id = client.submit(
        base_image,
        command="/usr/local/bin/python3",
        args=["-u", "-"],
        stdin=Path(__file__).with_name("build_image.py").read_text(),
        timeout=300,
        networking=True,
        disposable=False,
        max_layer_bytes=2 * 1024**3,
        output_limit=1024**2,
    )
    record = {
        "operation_id": operation_id,
        "image": None,
        "base_image": base_image,
        "opencode_version": OPENCODE_VERSION,
    }
    manifest.write_text(json.dumps(record, indent=2))
    print(f"Runtime build: {operation_id}", flush=True)
    result = client.wait(operation_id, 420).execution_result(require_image=True)
    (output / "build.log").write_text(result.stdout + result.stderr)
    record["image"] = result.image
    manifest.write_text(json.dumps(record, indent=2))
    return result.image
