"""Exercise examples and their independent checks through the returned program's CLI."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1]


class ExampleTests(unittest.TestCase):
    def test_create_reference_passes_and_wrong_generated_result_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            shutil.copytree(DEMO / "references/create", workspace, dirs_exist_ok=True)
            shutil.copy(DEMO / "fixtures/create/expenses.csv", workspace)
            subprocess.run(
                [sys.executable, "summarize.py", "expenses.csv", "--output", "summary.json"],
                cwd=workspace,
                check=True,
                capture_output=True,
            )
            command = [sys.executable, str(DEMO / "checks/validate.py"), "create", str(workspace)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            (workspace / "summary.json").write_text("{}")
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)

    def test_repair_fixture_exposes_each_bug_and_reference_passes(self):
        tests = DEMO / "fixtures/repair/test_expenses.py"
        for name in ("decimal", "refund", "quoted"):
            for project, expected in (("fixtures/repair", 1), ("references/repair", 0)):
                with self.subTest(case=name, project=project):
                    result = subprocess.run(
                        [sys.executable, str(tests), f"ExpenseTests.test_{name}"],
                        cwd=DEMO / project,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(result.returncode, expected, result.stderr)
                    self.assertIn("Ran 1 test", result.stderr)

    def test_repair_reference_passes_independent_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "repair"
            shutil.copytree(DEMO / "references/repair", project)
            shutil.copy(DEMO / "fixtures/repair/expenses.csv", project)
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "expense_summary",
                    "expenses.csv",
                    "--output",
                    "summary.json",
                ],
                cwd=project,
                check=True,
                capture_output=True,
            )
            result = subprocess.run(
                [sys.executable, str(DEMO / "checks/validate.py"), "repair", str(workspace)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_extend_reference_passes_and_starter_lacks_directory_support(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "repair"
            shutil.copytree(DEMO / "references/extend", project)
            shutil.copytree(DEMO / "fixtures/extend/input", workspace / "input")
            for format_name in ("json", "csv"):
                target = workspace / "results" / format_name
                target.mkdir(parents=True)
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "expense_summary",
                        str(workspace / "input"),
                        "--format",
                        format_name,
                        "--output",
                        str(target / f"summary.{format_name}"),
                    ],
                    cwd=project,
                    check=True,
                    capture_output=True,
                )
            result = subprocess.run(
                [sys.executable, str(DEMO / "checks/validate.py"), "extend", str(workspace)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "expense_summary",
                    str(workspace / "input"),
                    "--output",
                    str(workspace / "starter.json"),
                ],
                cwd=DEMO / "references/repair",
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
