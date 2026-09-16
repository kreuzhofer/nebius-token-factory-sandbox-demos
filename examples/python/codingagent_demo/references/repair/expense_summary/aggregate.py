"""Aggregate exact decimal amounts, retaining refunds."""

from decimal import Decimal


def summarize(rows):
    totals = {}
    count = 0
    for row in rows:
        category = row["category"]
        totals[category] = totals.get(category, Decimal(0)) + Decimal(row["amount"])
        count += 1
    return {
        "categories": {key: f"{value:.2f}" for key, value in totals.items()},
        "total": f"{sum(totals.values(), Decimal(0)):.2f}",
        "count": count,
    }
