# Wallet transfers

Wallet(path,accounts=None) uses durable SQLite accounts and successful receipts. accounts seeds absent ids only; opening a new Wallet on the same file preserves committed balances and receipts. transfer(id,source,destination,amount,fail_at=None) returns {id,source,destination,amount,balances:{source:new balance,destination:new balance}}. id/source/destination are nonempty strings; amount is positive integer cents (bool rejected), distinct existing accounts. Invalid input raises TransferError with status 400; unknown account 404; insufficient funds 422; same successful id with different payload 409. Replay of same id and payload returns the original stored result, even after later transfers. Validation or failure changes neither balances nor receipts; failed requests are not reserved. fail_at='after_debit' or 'after_receipt' raises RuntimeError and rolls back all effects. Balance check, both writes and successful receipt are one transaction. Independent Wallet instances/concurrent debits cannot overdraw. balances() returns all current balances. create_app(wallet) exposes POST /transfers with JSON id,source,destination,amount and maps TransferError statuses; successful/replayed responses are 200. Test failure hooks are not an HTTP parameter.

## Verification

Run `pytest -q`. Start with the listed entry files and tests; starters intentionally contain a defect. A passing suite is evidence, not a substitute for explaining the invariant.

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: Balance validation, debit, credit and payload-bound successful receipt share one durable transaction.

### Part 1 — Repair all-or-nothing writes

Reproduce both injected failure points and verify balances and receipts roll back together.

Evidence to show:

- Both failure hooks roll back debit, credit and receipt together.

### Part 2 — Make retries and concurrency durable

Return immutable stored replay results, reject payload conflicts and prevent overdrafts across independent connections.

Evidence to show:

- Successful receipts replay the original result; payload reuse conflicts and independent concurrent debits cannot overdraw.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- A rolled-back receipt must not reserve its id or payload; the later successful payload becomes durable.

### Part 4 — Changed requirement — optional discussion

Add partial refunds referencing an original transfer. Enforce a cumulative refund cap, recipient direction and independent refund idempotency within one transaction.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
