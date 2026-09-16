"""Authoritative CLI checks, delivered separately from the agent's workspace."""

import csv
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


class ProjectChecks(unittest.TestCase):
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


class RepairChecks(ProjectChecks):
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


EXTENDED = {
    "categories": {"food, takeaway": "4.80", "supplies": "1.25"},
    "total": "6.05",
    "count": 6,
}
SECOND = (
    "date,category,amount\n2026-01-05,supplies,1.05\n"
    '2026-01-06,"food, takeaway",2.45\n2026-01-07,misc,not-a-number\n'
)


class ExtendChecks(ProjectChecks):
    def invoke(self, source, output, format_name=None):
        command = [sys.executable, "-m", "expense_summary", str(source), "--output", str(output)]
        if format_name:
            command += ["--format", format_name]
        return subprocess.run(
            command, cwd=WORKSPACE / "repair", capture_output=True, text=True, timeout=10
        )

    def check_outputs(self, output, format_name):
        if format_name == "json":
            actual = json.loads(output.read_text())
            self.assertEqual(actual, EXTENDED)
            self.assertEqual(list(actual["categories"]), ["food, takeaway", "supplies"])
        else:
            with output.open(newline="") as handle:
                self.assertEqual(
                    list(csv.reader(handle)),
                    [
                        ["category", "total"],
                        ["food, takeaway", "4.80"],
                        ["supplies", "1.25"],
                    ],
                )
        issues = json.loads((output.parent / "issues.json").read_text())
        self.assertEqual(len(issues), 1)
        self.assertEqual(Path(issues[0]["file"]).name, "b.csv")
        self.assertEqual(issues[0]["line"], 4)
        self.assertEqual(issues[0]["amount"], "not-a-number")
        self.assertTrue(issues[0]["message"])

    def test_generated_outputs(self):
        for format_name in ("json", "csv"):
            self.check_outputs(
                WORKSPACE / "results" / format_name / f"summary.{format_name}", format_name
            )

    def test_directory_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input"
            source.mkdir()
            (source / "a.csv").write_text(REGRESSION)
            (source / "b.csv").write_text(SECOND)
            for format_name in ("json", "csv"):
                output = root / format_name / f"summary.{format_name}"
                output.parent.mkdir()
                result = self.invoke(source, output, format_name)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.check_outputs(output, format_name)

    def test_filename_order_and_top_level_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input"
            source.mkdir()
            # Create in reverse order so filesystem insertion order is insufficient.
            (source / "z.csv").write_text("date,category,amount\n2026-01-01,z,bad-z\n")
            (source / "a.csv").write_text("date,category,amount\n2026-01-01,a,bad-a\n")
            (source / "m.csv").write_text("date,category,amount\n2026-01-01,valid,1.00\n")
            (source / "ignored.txt").write_text(REGRESSION)
            (source / "nested").mkdir()
            (source / "nested/hidden.csv").write_text(REGRESSION)
            output = root / "summary.json"
            result = self.invoke(source, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            issues = json.loads((root / "issues.json").read_text())
            self.assertEqual([Path(item["file"]).name for item in issues], ["a.csv", "z.csv"])
            self.assertEqual(json.loads(output.read_text())["count"], 1)

    def test_legacy_single_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input.csv", root / "summary.json"
            source.write_text(REGRESSION)
            result = self.invoke(source, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text()), REPAIR)
            self.assertEqual(json.loads((root / "issues.json").read_text()), [])

    def test_missing_input_and_no_valid_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "empty").mkdir()
            (root / "invalid.csv").write_text("date,category,amount\n2026-01-01,x,bad\n")
            for name in ("missing.csv", "empty", "invalid.csv"):
                with self.subTest(input=name):
                    result = self.invoke(root / name, root / "out.json")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertTrue((result.stdout + result.stderr).strip())


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        {"create": CreateChecks, "repair": RepairChecks, "extend": ExtendChecks}[STAGE]
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
