"""Run Python receipt agents across orchestrated Nebius Sandboxes."""

import argparse
import json
from pathlib import Path

from configuration import ROOT, SandboxConfig, load_env
from nebius_sandbox import SandboxClient

from receipt_demo.artifacts import retrieve_result
from receipt_demo.configuration import InferenceConfig
from receipt_demo.sandbox import python_image, submit_worker, upload_code, worker_image

FIXTURES = ROOT.parent.parent / "fixtures" / "receipts"


def inputs_for_run(paths, profile):
    if paths:
        return [(f"input-{i:03}", Path(path), "") for i, path in enumerate(paths, 1)]
    root = FIXTURES
    manifest = json.loads((root / "manifest.json").read_text())
    selected = manifest["profiles"].get(profile)
    if selected is None:
        raise ValueError("Unknown profile; choose " + ", ".join(manifest["profiles"]))
    by_id = {item["input_id"]: item for item in manifest["inputs"]}
    credits = {}
    for source in json.loads((root / "public-sources.json").read_text()):
        credits[source["receipt_id"]] = "\n".join(
            str(source.get(key, ""))
            for key in (
                "author",
                "credit",
                "source_page",
                "license",
                "license_url",
                "local_modifications",
                "upstream_modifications",
            )
        )
    # Only file, input identity, and publication credit leave the launcher.
    # No expected values, source groups, or synthetic recipes enter agent context.
    return [
        (key, root / by_id[key]["path"], credits.get(key, "Synthetic demo receipt"))
        for key in selected
    ]


def main():
    parser = argparse.ArgumentParser(prog="python -m receipt_demo", description=__doc__)
    parser.add_argument(
        "inputs", nargs="*", help="Receipt files; defaults to a shared fixture profile"
    )
    parser.add_argument("--profile", default="demo")
    parser.add_argument("--output", default="receipt-output", type=Path)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--image", help="Existing Python 3.12 sandbox image")
    parser.add_argument(
        "--retrieve",
        help="Retry retrieval from a completed coordinator filesystem image, without inference",
    )
    parser.add_argument(
        "--timeout", default=1800, type=int, help="Sandbox seconds, including dependency setup"
    )
    parser.add_argument(
        "--concurrency", type=int, default=3, help="Maximum concurrent receipt jobs (1–8)"
    )
    parser.add_argument(
        "--child-timeout", type=int, default=600, help="Seconds per child job, including setup"
    )
    args = parser.parse_args()
    if not 300 <= args.timeout <= 3600:
        parser.error("--timeout must be between 300 and 3600 seconds")
    if not 1 <= args.concurrency <= 8 or not 300 <= args.child_timeout <= 1800:
        parser.error("--concurrency must be 1–8 and --child-timeout must be 300–1800 seconds")
    values = load_env(args.env_file)
    sandbox = SandboxConfig.from_env(values)
    api = SandboxClient(sandbox.token, sandbox.project, sandbox.base_url)
    args.output.mkdir(parents=True, exist_ok=True)
    if any((args.output / name).exists() for name in ("result.json", "report.json", "report.pdf")):
        raise RuntimeError("Choose a fresh output directory to preserve previous results")
    image = args.retrieve
    if not image:
        inference = InferenceConfig.from_env(values)
        sources = inputs_for_run(args.inputs, args.profile)
        if not sources or len(sources) > 30:
            raise ValueError("Supply between 1 and 30 receipts")
        if sum(path.stat().st_size for _, path, _ in sources) > 50 * 1024 * 1024:
            raise ValueError("Receipt inputs exceed the 50 MiB demo limit")
        image = python_image(api, args.image or values.get("CONTREE_IMAGE"))
        files, inputs = {}, []
        for receipt_id, path, credit in sources:
            remote = "/app/inputs/" + receipt_id + path.suffix.lower()
            files[remote] = api.upload(path.read_bytes())
            inputs.append(
                {"receipt_id": receipt_id, "source": path.name, "path": remote, "credit": credit}
            )
        files.update(upload_code(api, ROOT))
        files["/app/inputs.json"] = api.upload(json.dumps(inputs).encode())
        files["/app/workflow.json"] = api.upload(
            json.dumps(
                {
                    "role": "coordinator",
                    "image": image,
                    "concurrency": args.concurrency,
                    "child_timeout": args.child_timeout,
                }
            ).encode()
        )
        env = dict(inference.to_env(), **sandbox.to_env())
        operation = submit_worker(api, image, files, env, args.timeout)
        print(f"Coordinator job: {operation}", flush=True)
        (args.output / "job.json").write_text(
            json.dumps({"operation_id": operation, "image": None}, indent=2)
        )
        image = worker_image(api.wait(operation, args.timeout + 120))
        (args.output / "job.json").write_text(
            json.dumps({"operation_id": operation, "image": image}, indent=2)
        )
        print(f"Coordinator filesystem: {image}; retrieving artifacts", flush=True)
    response = retrieve_result(api, image, args.output)
    print(f"{response['status']}: {args.output.resolve()}", flush=True)
    if response["status"] == "failed":
        raise RuntimeError("Coordinator returned a failed run; see result.json")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # SDK/API exceptions may include prompts or credentials; expose our safe messages only.
        print(f"{type(exc).__name__}: {exc}")
        raise SystemExit(1) from None
