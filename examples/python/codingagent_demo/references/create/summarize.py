"""Maintained reference for the create example; never supplied to its agent."""

import argparse
import csv
import json
from decimal import Decimal
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("input")
parser.add_argument("--output", required=True)
args = parser.parse_args()
totals = {}
count = 0
with open(args.input, newline="") as source:
    for row in csv.DictReader(source):
        category = row["category"]
        totals[category] = totals.get(category, Decimal(0)) + Decimal(row["amount"])
        count += 1
Path(args.output).write_text(
    json.dumps(
        {
            "categories": {key: f"{value:.2f}" for key, value in totals.items()},
            "total": f"{sum(totals.values(), Decimal(0)):.2f}",
            "count": count,
        }
    )
)
