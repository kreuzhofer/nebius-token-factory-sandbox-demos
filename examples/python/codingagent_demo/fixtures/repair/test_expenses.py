"""Original CLI regression checks; also delivered independently to validation jobs."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ExpenseTests(unittest.TestCase):
    def summarize(self, rows):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.csv"
            output = Path(directory) / "output.json"
            source.write_text("date,category,amount\n" + rows)
            result = subprocess.run(
                [sys.executable, "-m", "expense_summary", str(source), "--output", str(output)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(output.read_text())

    def test_decimal(self):
        result = self.summarize("2026-01-01,supplies,0.01\n" * 100)
        self.assertEqual(
            result, {"categories": {"supplies": "1.00"}, "total": "1.00", "count": 100}
        )

    def test_refund(self):
        result = self.summarize("2026-01-01,supplies,2.00\n2026-01-02,supplies,-1.00\n")
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["total"], "1.00")

    def test_quoted(self):
        result = self.summarize('2026-01-01,"food, takeaway",2.35\n')
        self.assertEqual(result["categories"], {"food, takeaway": "2.35"})


if __name__ == "__main__":
    unittest.main()
