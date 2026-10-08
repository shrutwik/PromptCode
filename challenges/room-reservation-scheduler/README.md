# Room reservations

A room service rejects back-to-back bookings and races two callers into one free slot. Repair interval semantics and implement atomic reservation.

## Contract

Bookings and requests are integer half-open intervals [start,end) with end>start. overlap is false at a touching endpoint. Scheduler validates and stores a copy of input bookings; existing overlaps are allowed and searched as a occupied union. find(duration,earliest,latest_end) returns [start,end] for the earliest fully fitting gap, or None; duration>0. reserve performs find and insert as one atomic operation; returned bookings are sorted. Failed validation/reservation does not change stored bookings. Locks may serialize callers for the single room.

## Getting started

```sh
pip install -r requirements.txt
pytest -q
```

Start with README.md, contracts.py, engine.py and tests/test_engine.py. Preserve public signatures and the frozen tests. For extra experiments use a candidate-owned scratch.py. Do not change runner configuration to obtain a pass.

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: A calendar is an interval union; find and insert form one atomic reservation.

### Part 1 — Repair interval boundaries

Distinguish touching half-open intervals from overlap and validate duration/window inputs.

Evidence to show:

- Touching intervals do not overlap; invalid durations/windows preserve the calendar.

### Part 2 — Find and reserve a gap

Handle nested bookings, earliest exact fits, bounded windows, input copies and concurrent insertion.

Evidence to show:

- Return the earliest bounded gap in the booking union; find and insertion are one atomic reservation.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- An unavailable reservation leaves the calendar intact; a later exact adjacent slot remains bookable.

### Part 4 — Changed requirement — optional discussion

Add cancellation and rescheduling by reservation id. Define which reservation is released and ensure a failed reschedule restores the original slot atomically.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
