# Order hold

You are on the orders API during a warehouse freeze.

Support puts an order on hold with a reason. The next read cannot say why it is held, or the hold does not survive a refresh. Orders created before this field existed are still in the database.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

`POST /orders/:id/hold` with a `hold_reason` stores that reason and returns the order as `on_hold`. The following GET returns the same reason.

`POST /orders/:id/release` returns the order as `open`.

Orders that never had a reason come back with `hold_reason` null. Money is `total_cents`, an integer.

People are blaming the metrics counter. That is a hypothesis.

## Getting started

```bash
pip install -r requirements.txt
pytest -q
```

## Investigation checkpoints

This ticket tests: A successful response must describe persisted aggregate state, not echo the request. Verification focus: Trace hold, later GET, overwrite, release and another hold. Preserve money/customer fields and legacy nulls. Checkpoint 1: Reproduce the reported behavior and state the contract invariant. Checkpoint 2: Repair the smallest relevant path and verify preservation on success and rejection. Checkpoint 3: Defend your change with a counterexample and discuss the explicitly optional changed requirement.

## Optional review extension

Discuss concurrent edits and a version precondition; no new concurrency endpoint is required. This is discussion-only and does not alter baseline acceptance tests. Keep the supplied tests and configuration intact; use scratch.py or scratch.ts for independent experiments. Explain what you asked the assistant to do and which assumption you verified.
