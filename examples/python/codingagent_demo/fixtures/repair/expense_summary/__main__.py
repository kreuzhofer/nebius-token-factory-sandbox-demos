"""Public command: python -m expense_summary INPUT --output PATH."""

import argparse
import json
from pathlib import Path

from .aggregate import summarize
from .reader import read_rows

parser = argparse.ArgumentParser()
parser.add_argument("input")
parser.add_argument("--output", required=True)
args = parser.parse_args()
Path(args.output).write_text(json.dumps(summarize(read_rows(args.input))))
