"""Read CSV records, including quoted category names."""

import csv


def read_rows(path):
    with open(path, newline="") as source:
        yield from csv.DictReader(source)
