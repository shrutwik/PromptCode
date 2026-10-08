# SOLUTION — subscription-proration-boundary

## Root cause
`contains` uses inclusive end. Cancel at period.end still in-period.

## Investigation path
Existing mid-period cases stay green. The period-end case fails until `contains` treats `period.end` as outside.

## Reference implementation
```python
def contains(period: Period, instant: datetime) -> bool:
    return period.start <= instant < period.end
```

## Hidden evaluator cases
```python
def test_cancel_exactly_at_period_end_no_credit():
    period = period_from_iso("2024-01-01T00:00:00Z", "2024-02-01T00:00:00Z")
    sub = Subscription("s1", 3100, period)
    assert contains(period, period.end) is False
    assert proration_credit(sub, "2024-02-01T00:00:00Z") == 0
```

## Wrong alternatives
Patch display only; make start exclusive too.

## AI failure modes
1. Red-herring display fix.
2. Off-by-one both ends.

## Edge cases
Exact end; last second of period; DST display vs UTC storage.

## Verification
`pytest -q` is red on the period-end case until `contains` is half-open, then the suite is green.

## Complexity
Medium, 25–35 min. Looks-correct.

## Expected Event Timeline
| t | Event |
|---|---|
| 0–5 | All green — dig deeper |
| 5–15 | Ignore display; read contains |
| 15–25 | Half-open + regression |
| 25–35 | Defend |

## Positive signals
Invents boundary fixture despite green suite.

## Negative signals
Stops because tests pass; only touches display.

## Recovery signals
Writes cancel-at-end case after display patch.

## Interviewer Observations
Hypothesis quality under green tests.

## Rubric (100)
| ID | Criterion | Pts |
|---|---|---|
| A | Ignore display red herring | 15 |
| B | Find inclusive-end | 25 |
| C | Half-open fix | 20 |
| D | Start inclusive preserved | 15 |
| E | Boundary regression | 15 |
| F | Public tests green | 5 |
| G | Explanation | 5 |

## Derived Timeline Metrics
Display time <5m ideal; correct file <15m.

## Defend-Your-Code (4)
1. Q: Why end exclusive? A: Periods tile without overlap.
2. Q: Why tests passed? A: Missing boundary fixture.
3. Q: Display bug? A: Not on credit path.
4. Q: Credit formula? A: Membership gate was wrong.

## Deeper assessment insight

A stored instant has one period owner under half-open intervals; display timezone is separate from billing identity.

Check start, end, adjacent periods, equivalent offsets and microseconds, alongside an exact midpoint monetary calculation.

Plausible wrong repair: Returning zero for every cancellation fixes the endpoint example while destroying legitimate mid-period credits. Ask the candidate for a concrete failing example, not just an assertion that the shortcut is bad.

Changed requirement: Discuss a daylight-saving transition or non-monthly period using instants and elapsed duration; keep the baseline period contract. Keep this separate from baseline scoring and record the candidate reasoning and verification evidence.
