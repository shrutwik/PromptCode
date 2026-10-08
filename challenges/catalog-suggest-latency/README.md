# Search suggest

You are on catalog search. Shoppers typing in electronics wait long enough that suggest feels hung.

Product will ship a faster list only if it ranks the same products in the same order as today. The catalog in this repo is in memory, about 10,000 products, with id, title, category, popularity, and tokens.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

`suggest` stays in the current rank order: higher score, then higher popularity, then id ascending.

On the 10,000-product catalog the tests build, a query finishes in under 200ms and the scan counter stays under 20,000.

A cache in front of suggest is a hypothesis. Measure the work a query does before you add one.

## Getting started

```bash
npm install
npm test
```

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: An optimization may change work performed but must preserve the entire ranking and current data.

### Part 1 — Establish ranked parity

Capture score, popularity and id tie rules, normalized tokens, empty searches and exact limit behavior.

Evidence to show:

- Preserve score/popularity/id ordering, token normalization, empty output and prefix limits.

### Part 2 — Reduce measured work

Repair the service path; compare ranked outputs and operation counts before interpreting latency.

Evidence to show:

- Ranked outputs agree; verify real work and record calibrated latency, retaining the declared manual review requirements.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- A repeated query against changed data must reflect the new ranked winner and preserve prefix limits.

### Part 4 — Changed requirement — optional discussion

Add indexed catalogue updates or a query cache. Define invalidation/version ownership and show a changed-product query that detects stale results; counters still require independent review.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
