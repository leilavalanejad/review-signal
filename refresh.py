#!/usr/bin/env python3
"""
refresh.py: call the model for real and update ai_themes.json.

You do not need this to use the repo. `mine.py` runs on cached results with no
key and no account. This is only for pointing the tool at reviews the cache has
never seen.

    pip install anthropic
    export ANTHROPIC_API_KEY="sk-ant-..."
    python refresh.py -f my_reviews.json

THE KEY NEVER GOES IN A FILE IN THIS REPO. It's read from the environment. That
is the whole security model and it's enough: a key that is never written down
cannot be committed, and a key that is never committed cannot be scraped.

Anyone else who clones this repo and runs this uses their own key and pays
their own bill. There is no way for a stranger to spend your money through
this code.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
CACHE = HERE / "ai_themes.json"

# Model IDs change. If this one errors, the current list is at
# docs.anthropic.com, and you can override without editing code:
#   export ANTHROPIC_MODEL="..."
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")

BATCH = 20

PROMPT = """You are labelling app reviews for a competitive analysis.

Return a JSON array with one object per review, in the same order:
[{"theme": "...", "sentiment": "positive|negative|neutral"}]

Themes are what the reviewer is TALKING ABOUT, at the level a PM would put on
a slide: "Bank sync reliability", "Price increase backlash", "Support
responsiveness". Never "good" or "bad".

Two reviews on the same subject with opposite experiences are DIFFERENT themes
when the product implication differs. Praise for fast support and complaints
about slow support are not one theme.

Reuse theme names across reviews so they group. Use "Other" if nothing fits.

Return only the JSON array.

REVIEWS:
"""


def key(text):
    return hashlib.sha1(text.strip().lower().encode()).hexdigest()[:12]


def main():
    p = argparse.ArgumentParser(description="Refresh cached model results.")
    p.add_argument("-f", "--file", default=str(HERE / "reviews.json"))
    p.add_argument("--yes", action="store_true",
                   help="Skip the confirmation prompt")
    args = p.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\nNo ANTHROPIC_API_KEY found in your environment.\n")
        print("  export ANTHROPIC_API_KEY=\"sk-ant-...\"\n")
        print("See the README for where to get one. Nothing has been spent.\n")
        sys.exit(1)

    try:
        import anthropic
    except ImportError:
        print("\nThe anthropic package isn't installed.\n")
        print("  pip install anthropic\n")
        sys.exit(1)

    reviews = json.loads(Path(args.file).read_text())["reviews"]
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else \
        {"assignments": {}}
    todo = [r for r in reviews if key(r["text"]) not in cache["assignments"]]

    if not todo:
        print(f"\nAll {len(reviews)} reviews are already cached. "
              "Nothing to do, nothing spent.\n")
        return

    batches = (len(todo) + BATCH - 1) // BATCH
    print(f"\n{len(todo)} reviews need labelling, in {batches} "
          f"call{'s' if batches > 1 else ''} to {MODEL}.")
    print("Short reviews are cheap. Expect cents, not dollars, but check your")
    print("console for real numbers and set a spending limit there.\n")

    if not args.yes and input("  Go ahead? [y/N] ").strip().lower() != "y":
        print("\n  Stopped. Nothing spent.\n")
        return

    client = anthropic.Anthropic()
    added = 0

    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        numbered = "\n".join(
            f"{n + 1}. [{r['rating']} stars] {r['text']}"
            for n, r in enumerate(chunk))
        print(f"  batch {i // BATCH + 1}/{batches}...", end=" ", flush=True)

        msg = client.messages.create(
            model=MODEL, max_tokens=4000,
            messages=[{"role": "user", "content": PROMPT + numbered}])
        raw = msg.content[0].text.strip()
        raw = raw[raw.index("["):raw.rindex("]") + 1]
        labels = json.loads(raw)

        if len(labels) != len(chunk):
            print(f"\n  Model returned {len(labels)} labels for "
                  f"{len(chunk)} reviews. Skipping this batch rather than "
                  "guessing which is which.")
            continue

        for r, lab in zip(chunk, labels):
            cache["assignments"][key(r["text"])] = {
                "theme": lab.get("theme", "Other"),
                "sentiment": lab.get("sentiment", "neutral"),
            }
            added += 1
        print("ok")

    cache.setdefault("generated_with", f"{MODEL}, prompt in refresh.py")
    cache["key"] = "sha1(text.strip().lower())[:12]"
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n")
    print(f"\n  Cached {added} new reviews. Run: python mine.py -f "
          f"{args.file}\n")


if __name__ == "__main__":
    main()
