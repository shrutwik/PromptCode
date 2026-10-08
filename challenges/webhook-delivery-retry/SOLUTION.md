# SOLUTION — webhook-delivery-retry

## Root cause
`recordCharge` on every attempt; `deliverAll` uses unbounded Promise.all.

## Investigation path
Failing chargeCount / maxInFlight tests → worker.ts.

## Reference implementation
Move `recordCharge` to success path; pool concurrency limit 5 for deliverAll.

## Wrong alternatives
Remove retries; sleep without fixing side effect.

## AI failure modes
1. Leave Promise.all blast.
2. Add header only; still charge each attempt.

## Edge cases
All attempts fail → no charge.

## Verification
`npm test`

## Complexity
Medium, 30–35 min. Mild progressive A/B.

## Expected Event Timeline
| t | Event |
|---|---|
| 0–5 | See failures |
| 5–15 | Move charge |
| 15–30 | Concurrency pool |
| 30–35 | Re-run |

## Positive signals
Separates retry from commit.

## Negative signals
Queue system rewrite.

## Recovery signals
Instruments chargeCount after header-only attempt.

## Interviewer Observations
Idempotency vs once-on-success.

## Rubric (100)
| ID | Criterion | Pts |
|---|---|---|
| A | Single charge | 25 |
| B | Retries work | 15 |
| C | Concurrency ≤5 | 25 |
| D | No charge on failure | 10 |
| E | Scope | 10 |
| F | Promise.all reasoning | 10 |
| G | Verification | 5 |

## Derived Timeline Metrics
Part A <15m; Part B <35m.

## Parts and reviewer evidence

Billing identity belongs to a delivery; attempts and batch positions are separate identities.

- Part 1 (Trace one delivery): retry-charge-once, attempts-bounded.
- Part 2 (Deliver a bounded batch): flush-concurrency, exhausted-retries-charge-once, mixed-batch-result-order.
- Part 3 (Pressure-test the model): repeat-delivery-idempotent, duplicate-batch-identity.

Part 3 checks this contract property: Duplicate delivery ids in one concurrent batch share billing identity but keep one result per job. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: Every job instance or HTTP attempt owns a separate billing effect. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: Persist idempotency across restarts and handle a receiver that commits before its reply is lost. Define the idempotency key/payload policy and identify what requires receiver cooperation before claiming exactly-once effects. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: Charge before post? A: Failed attempts must not bill.
2. Q: Set vs move? A: Either; move simplest.
3. Q: Why 5? A: Acceptance.
4. Q: Promise.all always wrong? A: Dangerous unbounded IO.

## Deeper assessment insight

Attempt identity differs from delivery identity, and bounded concurrency differs from result order.

Run the same delivery id twice, exhaust retries, and process mixed success/failure batches. Charge once per delivery processing even if every attempt fails.

Plausible wrong repair: Charging only on success violates exhausted-delivery accounting; charging on each attempt duplicates the per-delivery effect. Ask the candidate for a concrete failing example, not just an assertion that the shortcut is bad.

Changed requirement: Discuss a worker restart and durable idempotency, plus what happens when the receiver processes a request but the response is lost. Keep this separate from baseline scoring and record the candidate reasoning and verification evidence.
