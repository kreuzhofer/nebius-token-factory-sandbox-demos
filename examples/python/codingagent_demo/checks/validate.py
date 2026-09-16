"""Authoritative CLI checks, delivered separately from the agent's workspace."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

STAGE = sys.argv.pop(1)
WORKSPACE = Path(sys.argv.pop(1)).resolve()
CREATE = {"categories": {"books": "20.00", "food": "10.00"}, "total": "30.00", "count": 4}


class CreateChecks(unittest.TestCase):
    def test_generated_files_and_rerun(self):
        self.assertTrue((WORKSPACE / "expenses.csv").is_file())
        self.assertEqual(json.loads((WORKSPACE / "summary.json").read_text()), CREATE)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "summary.json"
            result = subprocess.run(
                [sys.executable, "summarize.py", "expenses.csv", "--output", str(output)],
                cwd=WORKSPACE,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text()), CREATE)


REPAIR = {"categories": {"supplies": "0.20", "food, takeaway": "2.35"}, "total": "2.55", "count": 4}
REGRESSION = (
    "date,category,amount\n2026-01-01,supplies,0.10\n"
    "2026-01-02,supplies,0.20\n2026-01-03,supplies,-0.10\n"
    '2026-01-04,"food, takeaway",2.35\n'
)


class RepairChecks(unittest.TestCase):
    def test_original_tests(self):
        tests = Path(__file__).with_name("test_expenses.py")
        if not tests.exists():
            tests = Path(__file__).resolve().parents[1] / "fixtures/repair/test_expenses.py"
        result = subprocess.run(
            [sys.executable, str(tests), "-v"],
            cwd=WORKSPACE / "repair",
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_generated_summary_and_regression(self):
        project = WORKSPACE / "repair"
        self.assertEqual(json.loads((project / "summary.json").read_text()), REPAIR)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.csv"
            output = Path(directory) / "summary.json"
            source.write_text(REGRESSION)
            result = subprocess.run(
                [sys.executable, "-m", "expense_summary", str(source), "--output", str(output)],
                cwd=project,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text()), REPAIR)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        {"create": CreateChecks, "repair": RepairChecks}[STAGE]
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
