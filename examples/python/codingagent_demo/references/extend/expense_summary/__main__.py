"""Reference solution for directory input and explicit invalid-row reporting."""

import argparse
import csv
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    args = parser.parse_args()
    sources = sorted(args.input.glob("*.csv")) if args.input.is_dir() else [args.input]
    totals, issues = {}, []
    count = 0
    for source in sources:
        with source.open(newline="") as handle:
            for line, row in enumerate(csv.DictReader(handle), 2):
                try:
                    amount = Decimal(row["amount"])
                    if not amount.is_finite():
                        raise InvalidOperation
                except (InvalidOperation, ValueError, TypeError):
                    issues.append(
                        {
                            "file": source.name,
                            "line": line,
                            "amount": row["amount"],
                            "message": "Invalid amount",
                        }
                    )
                    continue
                category = row["category"]
                totals[category] = totals.get(category, Decimal(0)) + amount
                count += 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    (args.output.parent / "issues.json").write_text(json.dumps(issues))
    if not count:
        raise ValueError("No valid records")
    categories = {name: f"{totals[name]:.2f}" for name in sorted(totals)}
    if args.format == "json":
        args.output.write_text(
            json.dumps(
                {
                    "categories": categories,
                    "total": f"{sum(totals.values(), Decimal(0)):.2f}",
                    "count": count,
                }
            )
        )
    else:
        with args.output.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["category", "total"])
            writer.writerows(categories.items())


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
