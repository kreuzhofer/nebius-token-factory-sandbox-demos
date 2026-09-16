"""Read expense records (contains an intentional exercise bug)."""


def read_rows(path):
    with open(path) as source:
        next(source)
        for line in source:
            date, category, amount = line.strip().split(",")
            yield {"date": date, "category": category, "amount": amount}
