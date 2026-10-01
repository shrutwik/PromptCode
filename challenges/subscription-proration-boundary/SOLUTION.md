# SOLUTION — subscription-proration-boundary

## Root cause
`contains` uses inclusive end. Cancel at period.end still in-period.

## Investigation path
Public tests pass → probe cancel_at == end → period.contains.

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
Public pytest green; hidden boundary cases pass after fix.

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
