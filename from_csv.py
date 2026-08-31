#!/usr/bin/env python3
"""
from_csv.py: turn a spreadsheet of reviews into the JSON this tool reads.

Hand-writing JSON is a bad ask. Build the list in Excel or Google Sheets,
export as CSV, run this.

    python from_csv.py my_reviews.csv

Your sheet needs four columns with these exact headers, in any order:

    product   the app name, exactly two distinct values across the file
    rating    1 to 5
    date      YYYY-MM-DD
    text      the review itself

Twenty to thirty reviews per product is plenty. This tool is looking for
themes, not doing statistics.

Nothing here talks to the internet. You collect the reviews; this just
reformats them.
"""

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

REQUIRED = ["product", "rating", "date", "text"]


def die(msg):
    print(f"\n  {msg}\n")
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        die("Usage: python from_csv.py my_reviews.csv")

    src = Path(sys.argv[1])
    if not src.exists():
        die(f"Can't find {src}. Check the name, or drag the file into Terminal "
            "after typing the command.")

    out = src.with_suffix(".json")
    rows, problems = [], []

    with open(src, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = [h.strip().lower() for h in (reader.fieldnames or [])]
        missing = [c for c in REQUIRED if c not in headers]
        if missing:
            die(f"Your CSV is missing these columns: {', '.join(missing)}\n"
                f"  Found: {', '.join(headers) or 'nothing'}")

        for n, raw in enumerate(reader, start=2):
            row = {k.strip().lower(): (v or "").strip()
                   for k, v in raw.items() if k}
            if not row.get("text"):
                continue

            try:
                rating = int(float(row["rating"]))
            except (ValueError, KeyError):
                problems.append(f"row {n}: rating '{row.get('rating')}' "
                                "isn't a number 1 to 5")
                continue
            if not 1 <= rating <= 5:
                problems.append(f"row {n}: rating {rating} is outside 1 to 5")
                continue

            date = row.get("date", "")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                problems.append(f"row {n}: date '{date}' isn't YYYY-MM-DD. "
                                "Format the column as plain text in your sheet, "
                                "not as a date")
                continue

            rows.append({"product": row["product"], "rating": rating,
                         "date": date, "text": row["text"]})

    if problems:
        print(f"\n  Skipped {len(problems)} rows:\n")
        for p in problems[:10]:
            print(f"    {p}")
        if len(problems) > 10:
            print(f"    and {len(problems) - 10} more")
        print()

    if not rows:
        die("No usable rows. Check the column headers and try again.")

    counts = Counter(r["product"] for r in rows)
    if len(counts) != 2:
        print(f"\n  Heads up: found {len(counts)} products, and the tool needs "
              "exactly two.")
        for prod, n in counts.most_common():
            print(f"    {prod}: {n}")
        print("  Usually this is a typo or a trailing space in the product "
              "column.\n")

    thin = [p for p, n in counts.items() if n < 10]
    if thin:
        print(f"  Only a handful of reviews for: {', '.join(thin)}. "
              "It'll run, but\n  themes get thin below about ten per product.\n")

    out.write_text(json.dumps({"reviews": rows}, indent=2, ensure_ascii=False)
                   + "\n")
    print(f"  Wrote {len(rows)} reviews to {out.name}")
    for prod, n in counts.most_common():
        print(f"    {prod}: {n}")
    print(f"\n  Next:  python refresh.py -f {out.name}")
    print(f"  Then:  python mine.py -f {out.name}\n")


if __name__ == "__main__":
    main()
