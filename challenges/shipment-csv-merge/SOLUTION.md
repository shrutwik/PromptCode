# SOLUTION — shipment-csv-merge

## Root cause
Dedupe by (shipment_id, status) while still adding qty for skipped rows; should dedupe by event_id.

## Investigation path
Boundary tests fail → merge.py.

## Reference implementation
Sort (shipment_id, ts, event_id); dedupe by event_id; qty once.

## Wrong alternatives
Dedupe by status.

## AI failure modes
1. Wrong sort key.
2. Drop legitimate same-status updates.

## Edge cases
Day-boundary duplicate event_id; repeated status labels.

## Verification
`pytest -q`

## Complexity
Medium, 25–35 min.

## Expected Event Timeline
| t | Event |
|---|---|
| 0–5 | Read merge |
| 5–15 | Spot bad dedupe |
| 15–25 | Fix |
| 25–35 | Boundary cases |

## Positive signals
event_id idempotency.

## Negative signals
CSV comma rabbit hole.

## Recovery signals
Returns to merge after parse tweaks.

## Interviewer Observations
Boundary fixtures.

## Rubric (100)
| ID | Criterion | Pts |
|---|---|---|
| A | Sort by ts | 20 |
| B | Dedupe event_id | 25 |
| C | No double-count | 20 |
| D | Keep same-status distinct | 15 |
| E | Regressions | 10 |
| F | Scope | 5 |
| G | Explanation | 5 |

## Derived Timeline Metrics
Root cause <12m; green <30m.

## Defend-Your-Code (4)
1. Q: Why event_id? A: Idempotent key.
2. Q: Why ts then id? A: Stable tie-break.
3. Q: CSV commas? A: Parser fine.
4. Q: Qty on dupes? A: Skip entire event.
