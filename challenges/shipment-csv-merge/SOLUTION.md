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

## Parts and reviewer evidence

Event id identifies one contribution; status and shipment id do not.

- Part 1 (Recover event identity): same-status-distinct-id, duplicate-id-once.
- Part 2 (Aggregate without leaked state): independent-shipments, empty-clears-state, ties-negative-and-multi-file-dedup, next-merge-replaces-totals.
- Part 3 (Pressure-test the model): unrelated-shipment-invariance.

Part 3 checks this contract property: Adding unrelated records and a replayed event must not change an existing shipment total. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: Summing all rows before deduplication or mixing aggregates across shipments is harmless. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: The same event id arrives with different content. Define whether to reject, quarantine or explicitly version the correction; the present baseline only defines exact replays, so do not silently invent first-wins semantics. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: Why event_id? A: Idempotent key.
2. Q: Why ts then id? A: Stable tie-break.
3. Q: CSV commas? A: Parser fine.
4. Q: Qty on dupes? A: Skip entire event.

## Deeper assessment insight

Event identity, ordering and quantity aggregation are separate responsibilities.

Repartition the same events across files and require equal results; distinguish duplicate event_id from repeated status and preserve input batches.

Plausible wrong repair: Deduplicating by status discards distinct scans; summing before deduplication counts a repeated physical event twice. Ask the candidate for a concrete failing example, not just an assertion that the shortcut is bad.

Changed requirement: Discuss conflicting payloads for the same event id and agree on a policy before implementing it; the baseline fixtures use matching duplicate records. Keep this separate from baseline scoring and record the candidate reasoning and verification evidence.
