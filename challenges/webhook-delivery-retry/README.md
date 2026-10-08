# Webhook retry

You are on outbound webhooks. Receivers sometimes answer 500, and the worker retries. Finance then sees the charge recorded twice for one delivery. A flush of the pending queue also made staging fall over.

Delivery is at-least-once. A retry after a 5xx is normal. The side effect has to survive that.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

A delivery that fails and then succeeds still records the charge once for that delivery id. Attempts stop at the retry policy’s max.

Flushing a batch keeps at most about five posts in flight at once.

Lowering the timeout is a hypothesis. The duplicate charge is the incident.

## Getting started

```bash
npm install
npm test
```

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: Billing identity belongs to a delivery; attempts and batch positions are separate identities.

### Part 1 — Trace one delivery

Reproduce a transient failure and separate one billing effect from multiple bounded HTTP attempts.

Evidence to show:

- One charge belongs to one delivery id; attempts never exceed policy, including exhaustion.

### Part 2 — Deliver a bounded batch

Preserve per-input outcomes while capping active posts and handling exhausted retries.

Evidence to show:

- At most five posts are active; one outcome remains in each input position.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- Duplicate delivery ids in one concurrent batch share billing identity but keep one result per job.

### Part 4 — Changed requirement — optional discussion

Persist idempotency across restarts and handle a receiver that commits before its reply is lost. Define the idempotency key/payload policy and identify what requires receiver cooperation before claiming exactly-once effects.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
