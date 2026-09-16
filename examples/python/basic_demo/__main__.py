"""Configure and run the small Nebius sandbox examples."""

import argparse
import getpass
import json
import os
from pathlib import Path

from configuration import ROOT, SandboxConfig, load_env
from http_transport import HttpTransport
from nebius_sandbox import SandboxClient


def execute(api, image, mode, env):
    operation_id = api.submit(
        image,
        command="/usr/local/bin/python3",
        args=["-", mode],
        stdin=Path(__file__).with_name("agent.py").read_text(),
        env=env,
        disposable=mode == "agent",
        networking=mode == "agent",
        timeout=360 if mode == "agent" else 30,
    )
    print(f"{mode} operation: {operation_id}", flush=True)
    result = api.wait(operation_id, 420).execution_result()
    for output in (result.stdout, result.stderr):
        if output:
            print(output, end="" if output.endswith("\n") else "\n")


def main():
    parser = argparse.ArgumentParser(prog="python -m basic_demo", description=__doc__)
    parser.add_argument(
        "command", choices=["configure", "images", "models", "smoke", "agent", "all"]
    )
    parser.add_argument(
        "--image",
        help="Existing sandbox image UUID or tag:NAME (must contain /usr/local/bin/python3)",
    )
    args = parser.parse_args()
    if args.command == "configure":
        if (ROOT / ".env").exists():
            raise RuntimeError(".env already exists; edit it to change credentials")
        token = getpass.getpass("Sandbox API token (hidden): ")
        project = input("Sandbox Project ID: ").strip()
        inference = getpass.getpass("Inference API key (blank uses sandbox token): ") or token
        model = input("Token Factory model ID (may be set later): ").strip()
        fd = os.open(ROOT / ".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as output:
            output.write(
                f"CONTREE_TOKEN={token}\nCONTREE_PROJECT={project}\nNEBIUS_API_KEY={inference}\nNEBIUS_MODEL={model}\n"
            )
        print("Credentials saved in .env with mode 0600")
        return
    values = load_env()
    if args.command == "models":
        token = values.get("NEBIUS_API_KEY")
        if not token:
            raise RuntimeError("Set NEBIUS_API_KEY first")
        api = HttpTransport(
            values.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1"), token
        )
        for model in api.request("GET", "/models")["data"]:
            print(model["id"])
        return
    config = SandboxConfig.from_env(values)
    api = SandboxClient(config.token, config.project, config.base_url)
    if args.command == "images":
        print(json.dumps(api.list_images(), indent=2))
        return
    env = {}
    if args.command in ("agent", "all"):
        for name in ("NEBIUS_API_KEY", "NEBIUS_MODEL"):
            if not values.get(name):
                raise RuntimeError(f"Set {name} before running the agent")
            env[name] = values[name]
    image = args.image or values.get("CONTREE_IMAGE")
    if not image:
        operation_id = api.import_image("docker://docker.io/library/python:3.12-slim")
        print(f"Image import operation: {operation_id}", flush=True)
        image = api.wait(operation_id, 360).image
        if not image:
            raise RuntimeError("Import succeeded without a result image UUID")
        print(f"Reuse image with --image {image}", flush=True)
    if args.command in ("smoke", "all"):
        execute(api, image, "smoke", {})
    if args.command in ("agent", "all"):
        execute(api, image, "agent", env)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Do not dump objects that could include credentials.
        print(f"{type(exc).__name__}: {exc}")
        raise SystemExit(1) from None
