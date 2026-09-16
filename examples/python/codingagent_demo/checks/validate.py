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


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase({"create": CreateChecks}[STAGE])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
