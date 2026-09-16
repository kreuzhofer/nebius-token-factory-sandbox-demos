"""Expense-report artifact references and verified retrieval."""

import hashlib
import json
from pathlib import Path


def artifact_refs(artifacts):
    refs = {}
    for name, path in artifacts.items():
        data = Path(path).read_bytes()
        if not data or (name.endswith(".pdf") and not data.startswith(b"%PDF-")):
            raise RuntimeError("Report agent returned invalid artifacts")
        refs[name] = {
            "path": str(path),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    return refs


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
