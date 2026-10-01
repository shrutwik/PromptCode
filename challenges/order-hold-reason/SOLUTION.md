# SOLUTION — order-hold-reason

## Root cause
Model persists `hold_reason`, but `to_public_dict` omits it from API responses.

## Investigation path
POST hold → GET missing field → inspect `to_public_dict`.

## Reference implementation
```python
def to_public_dict(order: Order) -> dict:
    return {
        "id": order.id,
        "customer_id": order.customer_id,
        "total_cents": order.total_cents,
        "status": order.status,
        "hold_reason": order.hold_reason,
    }
```

## Wrong alternatives
Required non-null hold_reason; renaming fields.

## AI failure modes
1. Over-validation requiring reason.
2. Scope explosion / fake SQL migrations.

## Edge cases
Release nulls reason; explicit null on hold allowed.

## Verification
`pytest -q` — ticket test passes.

## Complexity
Medium, 25–30 min. Progressive A/B.

## Expected Event Timeline
| t | Event |
|---|---|
| 0–5 | Fail round-trip test |
| 5–15 | Find omission |
| 15–25 | Expose field |
| 25–30 | Legacy null check |

## Positive signals
Additive optional field.

## Negative signals
Required string breaking legacy.

## Recovery signals
Relaxes validation after 422.

## Interviewer Observations
Treats Part A/B as additive API change.

## Rubric (100)
| ID | Criterion | Pts |
|---|---|---|
| A | Persist reason | 15 |
| B | Expose API | 20 |
| C | Legacy null | 20 |
| D | Release clears | 10 |
| E | No breaking renames | 10 |
| F | Tests | 15 |
| G | Scope | 10 |

## Derived Timeline Metrics
Locate omission <10m; green <30m.

## Defend-Your-Code (4)
1. Q: Why null not omit? A: Stable key.
2. Q: Empty reason? A: Allowed by ticket.
3. Q: DB migrate? A: Field already on model.
4. Q: Required OpenAPI? A: Optional default null.
