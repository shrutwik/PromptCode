# Shipment CSV

You own the nightly shipment merge. Warehouse drops two CSV files that landed out of order. A shipment timeline showed a later status before an earlier one, and a quantity that should have been counted once was counted twice.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

Events from separate files come out in timestamp order for each shipment. The same `event_id` in two files counts once. Two events with the same status and different ids both stay, in timestamp order.

A teammate thinks a comma inside a CSV field broke the parser. That is a hypothesis.

## Getting started

```bash
pip install -r requirements.txt
pytest -q
```

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: Event id identifies one contribution; status and shipment id do not.

### Part 1 — Recover event identity

Reproduce duplicate replay versus distinct same-status events and preserve deterministic timeline order.

Evidence to show:

- Distinct same-status events remain; an exact replay contributes once.

### Part 2 — Aggregate without leaked state

Deduplicate before quantities, handle ties/negative deltas and replace totals on subsequent/empty merges.

Evidence to show:

- Quantities include negative deltas, isolate shipments and replace previous merge state, including empty input.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- Adding unrelated records and a replayed event must not change an existing shipment total.

### Part 4 — Changed requirement — optional discussion

The same event id arrives with different content. Define whether to reject, quarantine or explicitly version the correction; the present baseline only defines exact replays, so do not silently invent first-wins semantics.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
