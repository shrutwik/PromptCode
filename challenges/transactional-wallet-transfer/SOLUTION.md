# SOLUTION — transactional-wallet-transfer

## Reference approach and limits

Use a durable receipt keyed by request id and exact payload. BEGIN IMMEDIATE serializes the balance check and both updates across independent connections. Store the successful result inside the same transaction, then replay that exact result. Roll back every exception, including failure after receipt insertion. Balance conservation alone is insufficient: verify destination, request identity and retry outcome. SQLite is the contract implementation, not a simulation with only an in-memory lock.

Reviewed implementations are in backend/tests/ranked_reference_fixtures.py and remain interviewer/test-only.

## Initial incident

`engine.py` contains the faulty change `except Exception:db.commit();raise`. Repair the contract rather than changing expectations.

The transaction incident requires checking both injected failure points and separate connections.

## Independent evidence

Eight server-owned observation probes cover this family; expected values never enter the candidate command. Two plausible wrong repairs are checked separately. Rendered frontend behavior retains explicit reviewer requirements even when the visible suite passes.

## Rubric (100)

Correct behavior and preservation: 35; model and explanation: 25; independent verification: 20; AI-output review and trade-offs: 20. This guide does not replace the platform rubric.

## Parts and reviewer evidence

Balance validation, debit, credit and payload-bound successful receipt share one durable transaction.

- Part 1 (Repair all-or-nothing writes): rollback-debit, rollback-receipt, insufficient.
- Part 2 (Make retries and concurrency durable): move, durable-replay, conflict, no-overdraw, http-status.
- Part 3 (Pressure-test the model): failed-receipt-reusable.

Part 3 checks this contract property: A rolled-back receipt must not reserve its id or payload; the later successful payload becomes durable. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: An idempotency receipt can survive a rolled-back balance transaction and reserve that failed payload. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: Add partial refunds referencing an original transfer. Enforce a cumulative refund cap, recipient direction and independent refund idempotency within one transaction. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: Which operations share the transaction? A: Receipt check, balance validation, debit, credit and successful receipt insertion; a rollback removes all effects.
2. Q: Why return the stored result on replay? A: A retry is the same operation; later transfers must not change the result originally returned for that request.
3. Q: Why is request id alone insufficient? A: Reusing an id for a different source, destination or amount must conflict rather than authorize a new transfer.
4. Q: Why test independent Wallet instances? A: An object-local lock would not protect separate connections or a restart; durable transaction locking must prevent overdraw.
