"""Run Python receipt agents across orchestrated Nebius Sandboxes."""

import argparse
import json
import os
from pathlib import Path

from demo import ROOT, load_env
from receipt_demo.execution import BOOTSTRAP, INFERENCE_ENV
from sandbox_jobs import SandboxJobs, retrieve_result

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
    parser = argparse.ArgumentParser(description=__doc__)
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
    load_env(args.env_file)
    token = os.environ.get("CONTREE_TOKEN") or os.environ.get("NEBIUS_API_KEY")
    if not token:
        raise RuntimeError("Configure CONTREE_TOKEN or NEBIUS_API_KEY with demo.py configure")
    api = SandboxJobs(token, os.environ.get("CONTREE_PROJECT"), os.environ.get("CONTREE_BASE_URL"))
    args.output.mkdir(parents=True, exist_ok=True)
    if any((args.output / name).exists() for name in ("result.json", "report.json", "report.pdf")):
        raise RuntimeError("Choose a fresh output directory to preserve previous results")
    image = args.retrieve
    if not image:
        if not os.environ.get("NEBIUS_API_KEY"):
            raise RuntimeError("Set NEBIUS_API_KEY for Token Factory inference")
        sources = inputs_for_run(args.inputs, args.profile)
        if not sources or len(sources) > 30:
            raise ValueError("Supply between 1 and 30 receipts")
        if sum(path.stat().st_size for _, path, _ in sources) > 50 * 1024 * 1024:
            raise ValueError("Receipt inputs exceed the 50 MiB demo limit")
        image = api.python_image(args.image or os.environ.get("CONTREE_IMAGE"))
        files, inputs = {}, []
        for receipt_id, path, credit in sources:
            remote = "/app/inputs/" + receipt_id + path.suffix.lower()
            files[remote] = api.upload(path.read_bytes())
            inputs.append(
                {"receipt_id": receipt_id, "source": path.name, "path": remote, "credit": credit}
            )
        for path in (ROOT / "receipt_demo").iterdir():
            if path.suffix == ".py" or path.name == "requirements.txt":
                files["/app/receipt_demo/" + path.name] = api.upload(path.read_bytes())
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
        env = {key: os.environ[key] for key in INFERENCE_ENV if os.environ.get(key)}
        env["RECEIPT_JOB_TIMEOUT"] = str(args.timeout)
        for name in ("demo.py", "sandbox_jobs.py"):
            files["/app/" + name] = api.upload((ROOT / name).read_bytes())
        env["CONTREE_TOKEN"] = token
        for key in ("CONTREE_PROJECT", "CONTREE_BASE_URL"):
            if os.environ.get(key):
                env[key] = os.environ[key]
        operation, image = api.run(image, files, BOOTSTRAP, env, args.timeout)
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
