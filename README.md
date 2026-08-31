# Review Signal

Turns two products' reviews into the competitive brief you'd walk into a
meeting with.

```
$ python mine.py

COMPETITIVE BRIEF: Ledgerly vs Nestwell
60 reviews  (Ledgerly 30, Nestwell 30)


WHAT'S MOVING   most of this showed up in the last 6 weeks

  Price increase backlash  (Ledgerly)
    9 reviews, 9 recent, avg 1.7 stars
    "They raised the subscription and did not add a single feature. Feels
     like a bait and switch."

  Bank sync reliability  (Nestwell)
    8 reviews, 7 recent, avg 2.4 stars
    "Sync failure lost a week of transactions. Had to categorize everything
     by hand again."


WHERE THEY DIVERGE   one product owns this

  Interface and design   Ledgerly's strength
    Ledgerly 7, Nestwell 1   avg 4.6 stars
    "Best looking finance app I've used. Everything is where you expect it."

  Support quality   Nestwell's strength
    Nestwell 5   avg 4.8 stars
    "Emailed support on a Sunday and got a real answer Monday morning."


TABLE STAKES   both products, so it's the category

  Joint and shared accounts    Ledgerly 4, Nestwell 2   avg 2.8
  Reporting                    Ledgerly 3, Nestwell 1   avg 4.5
```

---

## Why this exists

Every review analyzer answers "what do people say," and the answer is always
mush, because the biggest theme in any corpus is "I like it" and the second
biggest is "I don't."

Three questions are actually useful, and none of them are that one.

**Where do we diverge?** A complaint both products share is the category's
problem, not yours. Everyone's bank sync is flaky. The signal is in what
skews to one side.

**What's changing?** A theme that's been steady for a year is background. One
that showed up six weeks ago is news, and it's the only kind you can still do
something about. Ledgerly's price backlash is nine reviews and all nine are
recent. That's not a rating, that's an event.

**Says who?** A theme without a verbatim is an assertion. Every line here
carries the quote it came from, because the quote is what you actually read
out loud in the meeting.

## The part I got wrong twice

I built the theme finder by clustering reviews on shared words. No model, no
key, runs anywhere. It's still in here as `--baseline`, and it doesn't work.

```
$ python mine.py --compare

  words   10 themes covering 33/60 reviews
  model   11 themes covering 59/60 reviews

  What the word version produced:

     7  good                             ratings 2 to 5
     5  support / account / again        ratings 1 to 4
     3  support / fixed / email          ratings 2 to 5
     3  solid                            ratings 3 to 4
     2  years                            ratings 2 to 5
```

Two things are wrong there and the second one is fatal.

It only reaches half the corpus, which is a tuning problem. I swept the
threshold and there's no good value: lower and single-link chaining collapses
forty reviews into one blob, higher and nothing groups at all.

But look at the star ranges. **Five of ten themes span three or more stars.**
A "theme" containing both a five-star rave and a one-star complaint isn't a
theme. And the reason is the whole lesson:

> "Support is the best I have dealt with in any app" and "Support took nine
> days to answer a billing question" share every content word and mean
> opposite things.

Word overlap groups by vocabulary. Vocabulary is not meaning. No amount of
tuning fixes that, because the information the clustering needs was never in
the token counts.

A model separates them, because separating them is a language problem:

```
  What the model produced:

     9  Price increase backlash          ratings 1 to 3
     8  Bank sync reliability            ratings 1 to 4
     8  Interface and design             ratings 4 to 5
     5  Support quality                  ratings 4 to 5
     3  Support responsiveness           ratings 1 to 2
```

Support quality and support responsiveness are two themes, correctly, and
their star ranges don't overlap at all.

## Why that's not the same conclusion I reached last time

I built [snack-check](https://github.com/leilavalanejad/snack-check) the same
way, regex against a model, and there the regex **won** on the labels I'd
tuned it against and only lost on formats it hadn't seen.

Two projects, opposite answers, and the difference is the shape of the
problem, not the size of it.

Pulling a number off a nutrition panel is **extraction**. The information is
already structured, it's just formatted inconsistently, and rules encode that
structure fine. Deciding whether two sentences are about the same subject is
**interpretation**. There's no structure to encode.

So the useful question was never "should I use AI here." It was "is the
information I need present in the surface form of the text." When it is, rules
are cheaper, faster and easier to debug. When it isn't, no amount of rules will
find it, and that's the case worth paying for.

I only know that because I built both and one of them lost.

## How it works

```
mine.py          themes, trends, skew, and the brief
reviews.json     60 reviews across two products
ai_themes.json   theme and sentiment per review, cached
```

Both products are **invented**. Mining and publishing a real company's reviews
means making claims about a real product, and this project is about the
analysis. Point `-f` at your own file to use it for real.

`ai_themes.json` is real model output, generated with the prompt in `mine.py`,
cached so **this runs with no API key and no account.** Clone it and
`--compare` works immediately.

The cache covers the 60 reviews shipped here. Point `-f` at your own file and
it tells you how many reviews it has no answers for, rather than inventing
some.

That message exists because of a bug worth admitting. The cache used to be
keyed by a review's position in the file, so loading your own reviews handed
review 3 whatever theme sample review 3 had. Reviews about PDF exports and
double billing came back labeled "Bank sync reliability," confidently, with no
error. It's keyed by a hash of the review text now, so an unseen review misses
and says so. A tool that quietly returns the wrong answer is worse than one
that admits it doesn't know.

## Usage

```bash
python mine.py                  # the brief
python mine.py --compare        # both theme engines, side by side
python mine.py --themes         # every theme, largest first
python mine.py --baseline       # the word-overlap version, for contrast
```

No dependencies beyond the standard library. Python 3.8+.

## Running it on real products

**This tool does not fetch reviews.** It has no scraper and no network access.
You bring the reviews; it does the analysis. That's a deliberate limit, not an
oversight: review sites have terms about automated collection, and the
interesting work here was never the fetching.

Collect twenty to thirty reviews per product by hand into a spreadsheet with
four columns, `product`, `rating`, `date`, `text`, then:

```bash
python from_csv.py my_reviews.csv    # spreadsheet to JSON, validates as it goes
python refresh.py -f my_reviews.json # labels them with a model, costs cents
python mine.py -f my_reviews.json    # the brief, free, and free every rerun
```

Only the middle step needs an API key. `from_csv.py` tells you which rows it
skipped and why, which is usually a date formatted as a date rather than as
text.

Twenty per product is enough. This is looking for themes, not doing statistics.

## What I'd do next

- **The trend window is fixed at six weeks.** Fine for this corpus, wrong for a
  product that ships quarterly. It should adapt to the release cadence.
- **Sentiment comes from the model, severity comes from star ratings.** Those
  disagree sometimes, and right now nothing notices when they do.
- **Sixty reviews is small.** At five thousand the model pass costs real money
  and a sample-then-extrapolate step starts earning its place.
- **No competitor discovery.** You have to know who to compare against. Working
  out who you're actually losing to is the harder question and this doesn't
  touch it.

---

Built by [Leila Valanejad](https://github.com/leilavalanejad).
