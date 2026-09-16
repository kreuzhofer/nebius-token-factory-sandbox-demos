"""Aggregate expenses (contains intentional exercise bugs)."""


def summarize(rows):
    totals = {}
    count = 0
    for row in rows:
        amount = float(row["amount"])
        if amount < 0:
            continue
        category = row["category"]
        totals[category] = totals.get(category, 0.0) + amount
        count += 1
    return {
        "categories": {key: str(value) for key, value in totals.items()},
        "total": str(sum(totals.values())),
        "count": count,
    }
