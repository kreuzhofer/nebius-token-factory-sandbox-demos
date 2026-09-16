"""Exercise task execution, independent checks, and reuse of one prepared image."""

import json
from pathlib import Path

from .helper import run_task

TASK = (
    "Fix the add function in proof/calculator.py so it adds both numbers. "
    "Do not change the tests. Run python3 -m unittest discover -s proof -v and "
    "report the actual output. Use shell and file tools to do the work."
)


def run_proof(client, config, image, output):
    """Run two fresh task jobs from one image, validating their returned code separately."""
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    fixture = Path(__file__).with_name("fixtures") / "proof"
    proof = {"runtime_image": image, "passed": False, "runs": []}
    try:
        for attempt in (1, 2):
            result = run_task(
                client,
                config,
                image,
                TASK,
                files=[fixture],
                output=output / f"task-{attempt}",
                timeout=300,
            )
            run = {"task": result, "validation": None}
            proof["runs"].append(run)
            if result["status"] != "completed":
                return proof
            # The reference tests come from the host fixture, never the agent's copy.
            files = {
                "/work/calculator.py": client.upload(
                    client.download(result["image"], "/workspace/proof/calculator.py")
                ),
                "/checks/test_calculator.py": client.upload(
                    (fixture / "test_calculator.py").read_bytes()
                ),
            }
            operation = client.submit(
                image,
                command="/usr/local/bin/python3",
                args=["-m", "unittest", "discover", "-s", "/checks", "-v"],
                cwd="/work",
                files=files,
                env={"PYTHONPATH": "/work"},
                timeout=60,
                networking=False,
                disposable=True,
            )
            run["validation"] = {"operation_id": operation, "passed": False}
            (output / "proof.json").write_text(json.dumps(proof, indent=2))
            print(f"Validation job: {operation}", flush=True)
            execution = client.wait(operation, 180).execution_result(check=False)
            run["validation"].update(
                passed=execution.successful, stdout=execution.stdout, stderr=execution.stderr
            )
            if not execution.successful:
                return proof
        proof["passed"] = True
        return proof
    finally:
        (output / "proof.json").write_text(json.dumps(proof, indent=2))
