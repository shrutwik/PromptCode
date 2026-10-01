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

## Defend-Your-Code (4)
1. Q: Charge before post? A: Failed attempts must not bill.
2. Q: Set vs move? A: Either; move simplest.
3. Q: Why 5? A: Acceptance.
4. Q: Promise.all always wrong? A: Dangerous unbounded IO.
