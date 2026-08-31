#!/usr/bin/env python3
"""
mine.py: read two products' reviews, produce the brief you'd walk into a
meeting with.

Not "what do people say." Every review tool answers that and the answer is
always mush, because the loudest theme in any corpus is "I like it" and the
second loudest is "I don't."

The three questions a PM actually has:

  Where do we diverge?  A complaint both products share is the category's
  problem, not yours. The signal is in what skews.

  What's changing?  A theme steady for a year is background. One that appeared
  six weeks ago is news, and it's the only kind you can still act on.

  Says who?  A theme without a verbatim is an assertion. Every line carries
  the quote it came from.

Two theme engines ship here. `--baseline` groups reviews by shared words, the
way I built it first. The default uses a model. `--compare` shows why that
turned out to be necessary rather than fashionable.
"""

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "of", "to", "in", "on", "at",
    "for", "with", "by", "from", "as", "is", "are", "was", "were", "be", "been",
    "it", "its", "this", "that", "these", "those", "there", "their", "they",
    "he", "she", "his", "her", "you", "your", "we", "our", "us", "i", "me",
    "my", "will", "would", "could", "should", "may", "might", "can", "has",
    "have", "had", "not", "no", "than", "then", "so", "also", "more", "most",
    "other", "app", "apps", "use", "used", "using", "just", "really", "very",
    "get", "got", "one", "two", "all", "any", "out", "up", "down", "about",
    "what", "which", "who", "when", "where", "how", "still", "even", "way",
    "thing", "things", "much", "many", "every", "some", "do", "does", "did",
    "am", "im", "ive", "dont", "didnt", "cant", "wont", "isnt",
}

# Overlap coefficient rather than Jaccard, because reviews are short and vary
# wildly in length. 0.30 chosen by sweeping: below it single-link chaining
# collapses half the corpus into one blob, above it nothing groups at all.
SAME_THEME = 0.30

RECENT_WEEKS = 6


def tokens(text):
    words = re.findall(r"[a-z][a-z']+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def similarity(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def load(path):
    data = json.loads(Path(path).read_text())
    for r in data["reviews"]:
        # Key on the text itself. Keying on position meant that pointing this
        # at your own reviews silently assigned them the sample's themes.
        r["_id"] = hashlib.sha1(r["text"].strip().lower().encode()).hexdigest()[:12]
        r["_tokens"] = tokens(r["text"])
        r["_date"] = datetime.strptime(r["date"], "%Y-%m-%d").date()
    return data["reviews"]


def themes_baseline(reviews):
    """
    Group by shared words. This is the version I built first and it does not
    work, for a reason worth stating: it groups by vocabulary, and vocabulary
    is not meaning. "Support is the best I've dealt with" and "support took
    nine days" share every content word and are opposite facts.
    """
    groups = []
    for r in reviews:
        for g in groups:
            if any(similarity(r["_tokens"], o["_tokens"]) >= SAME_THEME for o in g):
                g.append(r)
                break
        else:
            groups.append([r])

    out = []
    for g in groups:
        if len(g) < 2:
            continue
        counts = Counter()
        for r in g:
            counts.update(r["_tokens"])
        words = [w for w, n in counts.most_common(6) if n >= max(2, len(g) // 2)]
        out.append({"name": " / ".join(words[:3]) or "unlabeled", "reviews": g})
    return out


def themes_ai(reviews):
    """
    Theme and sentiment per review, from the cache. See PROMPT below.

    The cache is keyed by a hash of the review text, so reviews it has never
    seen miss cleanly and get reported. Anything else would mean handing your
    reviews the sample's answers, which is exactly what the first version did.
    """
    cache = json.loads((HERE / "ai_themes.json").read_text())["assignments"]
    buckets, missing = defaultdict(list), 0
    for r in reviews:
        a = cache.get(r["_id"])
        if not a:
            missing += 1
            continue
        if a["theme"] == "Other":
            continue
        r["_sentiment"] = a["sentiment"]
        buckets[a["theme"]].append(r)

    if missing:
        print(f"\n  {missing} of {len(reviews)} reviews aren't in the cached "
              f"model results.")
        print("  This repo ships cached answers for its own sample so it runs "
              "without an API key.")
        print("  For your own reviews you need a key, or use --baseline to see "
              "the word-matching\n  version (which the README explains does not "
              "work well).")
        if not buckets:
            print()
            return []
    return [{"name": k, "reviews": v} for k, v in buckets.items() if len(v) > 1]


def enrich(themes, products, reviews):
    latest = max(r["_date"] for r in reviews)
    cutoff = latest.toordinal() - RECENT_WEEKS * 7
    a, b = products

    for t in themes:
        g = t["reviews"]
        by = Counter(r["product"] for r in g)
        recent = [r for r in g if r["_date"].toordinal() >= cutoff]
        t["size"] = len(g)
        t["by_product"] = dict(by)
        t["skew"] = by.get(a, 0) - by.get(b, 0)
        t["recent"] = len(recent)
        t["recent_share"] = len(recent) / len(g)
        t["avg_rating"] = sum(r["rating"] for r in g) / len(g)
        # Quote the product that owns the theme. Attributing a theme to one
        # product and then quoting the other one reads as sloppy, and it is.
        owner = max(by, key=by.get)
        pool = [r for r in g if r["product"] == owner] or g
        t["quote"] = min(pool, key=lambda r: abs(len(r["text"]) - 95))
    return themes


# A brief nobody finishes reading is not a brief. Every section caps here for
# the same reason dinner-decider returns three meals: the job is to cut the
# options down. --themes still shows everything.
TOP_N = 3


def brief(themes, products, reviews):
    a, b = products
    counts = Counter(r["product"] for r in reviews)
    out = [f"\nCOMPETITIVE BRIEF: {a} vs {b}",
           f"{len(reviews)} reviews  ({a} {counts[a]}, {b} {counts[b]})"]

    moving = [t for t in themes if t["recent_share"] >= 0.55 and t["size"] >= 3]
    moving.sort(key=lambda t: (-t["recent_share"], -t["size"]))
    moving = moving[:TOP_N]
    if moving:
        out.append("\n\nWHAT'S MOVING   most of this showed up in the last "
                   f"{RECENT_WEEKS} weeks\n")
        for t in moving:
            owner = max(t["by_product"], key=t["by_product"].get)
            out.append(f"  {t['name']}  ({owner})")
            out.append(f"    {t['size']} reviews, {t['recent']} recent, "
                       f"avg {t['avg_rating']:.1f} stars")
            out.append(f"    \"{t['quote']['text'][:100]}\"")
            out.append("")

    diverge = [t for t in themes if abs(t["skew"]) >= 3]
    diverge.sort(key=lambda t: -abs(t["skew"]))
    diverge = diverge[:TOP_N]
    if diverge:
        out.append("\nWHERE THEY DIVERGE   one product owns this\n")
        for t in diverge:
            owner = a if t["skew"] > 0 else b
            verdict = "problem" if t["avg_rating"] < 3.5 else "strength"
            c = ", ".join(f"{p} {n}" for p, n in sorted(t["by_product"].items()))
            out.append(f"  {t['name']}   {owner}'s {verdict}")
            out.append(f"    {c}   avg {t['avg_rating']:.1f} stars")
            out.append(f"    \"{t['quote']['text'][:100]}\"")
            out.append("")

    shared = [t for t in themes if abs(t["skew"]) <= 2 and t["size"] >= 3][:TOP_N]
    if shared:
        out.append("\nTABLE STAKES   both products, so it's the category\n")
        for t in shared:
            c = ", ".join(f"{p} {n}" for p, n in sorted(t["by_product"].items()))
            out.append(f"  {t['name']:<28} {c}   avg {t['avg_rating']:.1f}")
        out.append("")
    return "\n".join(out)


def compare(reviews, products):
    base = enrich(themes_baseline(reviews), products, reviews)
    ai = enrich(themes_ai(reviews), products, reviews)

    print(f"\n{len(reviews)} reviews, two ways of finding themes.\n")
    print(f"  words   {len(base):>2} themes covering "
          f"{sum(t['size'] for t in base):>2}/{len(reviews)} reviews")
    print(f"  model   {len(ai):>2} themes covering "
          f"{sum(t['size'] for t in ai):>2}/{len(reviews)} reviews\n")

    print("  What the word version produced:\n")
    for t in sorted(base, key=lambda t: -t["size"]):
        span = f"{min(r['rating'] for r in t['reviews'])} to " \
               f"{max(r['rating'] for r in t['reviews'])}"
        print(f"    {t['size']:>2}  {t['name']:<32} ratings {span}")

    print("\n  What the model produced:\n")
    for t in sorted(ai, key=lambda t: -t["size"]):
        span = f"{min(r['rating'] for r in t['reviews'])} to " \
               f"{max(r['rating'] for r in t['reviews'])}"
        print(f"    {t['size']:>2}  {t['name']:<32} ratings {span}")

    mixed = [t for t in base
             if max(r["rating"] for r in t["reviews"]) -
                min(r["rating"] for r in t["reviews"]) >= 3]
    print(f"\n  {len(mixed)} of {len(base)} word-themes span 3+ stars, meaning "
          "praise and complaint\n  landed in the same bucket. That is the whole "
          "problem: word overlap groups\n  by vocabulary, and 'support was "
          "great' and 'support was slow' use the\n  same vocabulary.\n")


PROMPT = """You are labelling app reviews for a competitive analysis.

For each review return {"theme": "...", "sentiment": "positive|negative|neutral"}.

Themes should be about what the reviewer is TALKING ABOUT, at the level a PM
would put on a slide: "Bank sync reliability", "Price increase backlash",
"Support responsiveness". Not "good" or "bad".

Two reviews about the same subject but opposite experiences are DIFFERENT
themes if the product implication differs. Praise for fast support and
complaints about slow support are not one theme.

Use "Other" if it doesn't fit anything.
"""


def main():
    p = argparse.ArgumentParser(
        description="Turn two products' reviews into a competitive brief.")
    p.add_argument("-f", "--file", default=str(HERE / "reviews.json"),
                   help="Reviews JSON (default: the included sample)")
    p.add_argument("--baseline", action="store_true",
                   help="Use word-overlap clustering instead of the model")
    p.add_argument("--compare", action="store_true",
                   help="Run both and show why the model is here")
    p.add_argument("--themes", action="store_true",
                   help="Every theme, largest first")
    args = p.parse_args()

    reviews = load(args.file)
    products = sorted({r["product"] for r in reviews})
    if len(products) != 2:
        print(f"\nNeeds exactly two products, found {len(products)}.\n")
        return

    if args.compare:
        compare(reviews, products)
        return

    finder = themes_baseline if args.baseline else themes_ai
    themes = enrich(finder(reviews), products, reviews)

    if args.themes:
        print(f"\n{len(themes)} themes:\n")
        for t in sorted(themes, key=lambda t: -t["size"]):
            c = ", ".join(f"{p} {n}" for p, n in sorted(t["by_product"].items()))
            print(f"  {t['size']:>2}  avg {t['avg_rating']:.1f}  "
                  f"{t['recent']:>2} recent   {t['name']:<28} {c}")
        print()
        return

    print(brief(themes, products, reviews))


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass
