# Structured logger

A configurable logger filters severity incorrectly and one failed sink prevents other destinations from receiving events. Complete predictable emission and atomic configuration.

## Contract

Levels are DEBUG<INFO<WARN<ERROR; emit includes the threshold itself. Inject a clock and callable sinks; emit(level,message,context=None) returns a list of failed sink indices while continuing to other sinks. Records contain level,message,timestamp,context; deep-copy context at emission and give each sink its own deep copy. Unknown levels/configs raise ValueError before changing config or writing sinks. configure(level,sinks) affects future calls. Suppressed events call neither the injected clock nor sinks. JSON formatting must escape message contents and preserve structured values. Sink exceptions do not recursively log or get silently represented as success.

## Getting started

```sh
pip install -r requirements.txt
pytest -q
```

Start with README.md, contracts.py, engine.py and tests/test_engine.py. Preserve public signatures and the frozen tests. For extra experiments use a candidate-owned scratch.py. Do not change runner configuration to obtain a pass.

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: Threshold inclusion, sink isolation and configuration replacement each have their own failure boundary.

### Part 1 — Repair event eligibility

Verify exact thresholds, unknown-level rejection, clock injection and suppressed-event behavior.

Evidence to show:

- Thresholds are inclusive; unknown policies are rejected before writes and filtered events produce no records.

### Part 2 — Deliver isolated records

Continue after failed sinks and separate caller-owned context and per-sink nested data.

Evidence to show:

- Each sink receives copied nested data; failures are reported by index without stopping later sinks.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- Rejected configuration must preserve the prior policy; filtered events must not invoke the clock or sinks.

### Part 4 — Changed requirement — optional discussion

Allow asynchronous sinks. Specify backpressure, timeout/cancellation and failure reporting before adapting emit; a rejected promise must not be mistaken for successful delivery.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
