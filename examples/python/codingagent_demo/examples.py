"""Run reproducible coding examples and check returned files in a separate sandbox."""

import json
from pathlib import Path

from .helper import run_task

DEMO = Path(__file__).parent
STAGES = {
    "create": {
        "timeout": 300,
        "inputs": ["fixtures/create/expenses.csv"],
        "task": (
            "Create summarize.py in /workspace. It accepts an input CSV path and --output PATH. "
            "Use exact decimal arithmetic and format money as two-decimal strings. "
            "JSON must have categories (category to total mapping), total, and count. "
            "Run it on expenses.csv to write /workspace/summary.json. "
            "Test the script and report what you did."
        ),
    },
    "repair": {
        "timeout": 600,
        "inputs": ["fixtures/repair"],
        "task": (
            "Repair the project in /workspace/repair. Its command is python3 -m expense_summary "
            "INPUT --output PATH. Fix binary-float money handling, discarded refunds, and naive "
            "comma splitting. Use csv.DictReader for CSV parsing and decimal.Decimal for money; "
            "replace the broken parsing approach rather than patching string splitting. "
            "Preserve the JSON interface: categories, total, count; money must "
            "use exact decimal arithmetic and two-decimal strings. Do not change tests. "
            "Run python3 -m unittest discover -v from the project, then summarize expenses.csv "
            "to /workspace/repair/summary.json. Report actual test results."
        ),
    },
    "extend": {
        "timeout": 1800,
        "inputs": [
            "references/repair",
            "fixtures/extend/input",
            "fixtures/repair/test_expenses.py",
        ],
        "task": (
            "Extend the correct project in /workspace/repair. Preserve python3 -m expense_summary "
            "INPUT --output PATH and default JSON behavior. Add directory input: read only "
            "top-level .csv files in filename order. Add --format json|csv and sort categories. "
            "Keep csv.DictReader and decimal.Decimal. JSON has categories, total, count with "
            "two-decimal money strings. CSV has category,total header and category rows only, "
            "using csv.writer for normal CSV quoting, no grand-total row. Skip invalid amounts but retain valid "
            "rows and write issues.json beside EACH output: a list of objects with file (input "
            "filename), line (1-based, header is line 1), amount (original value), message "
            "(explanation). Write [] when there are no issues. Exit zero with valid rows even "
            "if there are issues; unreadable input or no valid records must exit nonzero with "
            "a diagnostic. Keep outputs outside input directories. Test the added features; "
            "run the original /workspace/test_expenses.py from the project without modifying it. "
            "Run on /workspace/input to generate /workspace/results/json/summary.json and "
            "/workspace/results/csv/summary.csv (each with issues.json alongside). "
            "For the supplied input, assert SIX valid records, total 6.05, and categories "
            "food, takeaway=4.80 and supplies=1.25. Each issues.json must contain exactly "
            "one object: file=b.csv, line=4, amount=not-a-number, plus an explanation. "
            "Parse the generated CSV with csv.reader and assert exactly a two-column header "
            "and two two-column category rows. Add and run tests for these new features, "
            "including error propagation and filename ordering, before finishing. "
            "Report the actual test results and generated outputs."
        ),
    },
}


def run_example(client, config, image, stage, output):
    """Run one fresh task and validate its archive, retaining both outcomes separately."""
    spec = STAGES[stage]
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    record = {
        "stage": stage,
        "runtime_image": image,
        "passed": False,
        "task": None,
        "validation": None,
        "error": None,
    }

    def save():
        (output / "example.json").write_text(json.dumps(record, indent=2))

    try:
        record["task"] = run_task(
            client,
            config,
            image,
            spec["task"],
            files=[DEMO / path for path in spec["inputs"]],
            output=output / "task",
            timeout=spec["timeout"],
        )
        save()
        if record["task"]["status"] != "completed":
            return record
        files = {
            "/checks/workspace.tar.gz": client.upload(Path(record["task"]["archive"]).read_bytes()),
        }
        for name in ("unpack.py", "validate.py"):
            files["/checks/" + name] = client.upload((DEMO / "checks" / name).read_bytes())
        files["/checks/test_expenses.py"] = client.upload(
            (DEMO / "fixtures/repair/test_expenses.py").read_bytes()
        )
        operation = client.submit(
            image,
            command="/usr/local/bin/python3",
            args=["/checks/unpack.py", stage],
            files=files,
            timeout=60,
            networking=False,
            disposable=True,
        )
        record["validation"] = {"operation_id": operation, "passed": False}
        save()
        print(f"Validation job: {operation}", flush=True)
        execution = client.wait(operation, 180).execution_result(check=False)
        record["validation"].update(
            passed=execution.successful,
            stdout=execution.stdout,
            stderr=execution.stderr,
        )
        record["passed"] = execution.successful
    except Exception as exc:
        record["error"] = f"Example failed: {type(exc).__name__}"
    finally:
        save()
    return record
