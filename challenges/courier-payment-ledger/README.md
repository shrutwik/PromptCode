# Courier payments

Courier payouts truncate sub-hour work. Restore exact delivery accounting, then complete incremental payments and distinct-driver activity reporting.

## Contract

Rates are nonnegative integer cents/hour; start/end are integer seconds, end>start. Cost is rounded half-up once per delivery from rate*(end-start)/3600. Delivery ids are unique; exact duplicate records are idempotent, conflicting reuse raises ValueError without changing the ledger. Unknown drivers are rejected. pay_up_to(cutoff) returns newly paid cents for deliveries with end<=cutoff; repeated cutoffs pay nothing twice. total and unpaid are integer cents. peak counts distinct drivers in [window_start,window_end), with delivery intervals half-open; overlapping jobs by one driver count once.

## Getting started

```sh
pip install -r requirements.txt
pytest -q
```

Start with README.md, contracts.py, engine.py and tests/test_engine.py. Preserve public signatures and the frozen tests. For extra experiments use a candidate-owned scratch.py. Do not change runner configuration to obtain a pass.

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: Rounded delivery costs, successful payments and distinct-driver activity are different aggregates.

### Part 1 — Recover precise amounts

Repair per-delivery half-up rounding using integer cents and reject invalid/conflicting records without mutation.

Evidence to show:

- Round each delivery half-up in integer cents; conflicting or invalid records preserve the ledger.

### Part 2 — Pay and measure activity

Implement completed-delivery cutoff payments and clipped half-open distinct-driver activity.

Evidence to show:

- Pay only unpaid deliveries completed by the cutoff; count distinct active drivers in a clipped half-open window.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- An earlier cutoff after a later payment cannot charge again or change ledger totals.

### Part 4 — Changed requirement — optional discussion

A completed delivery is corrected after payment. Design immutable adjustment records and idempotent refunds; explain how historical receipts and current unpaid amounts differ.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
