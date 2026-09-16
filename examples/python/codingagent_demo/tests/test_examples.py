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
