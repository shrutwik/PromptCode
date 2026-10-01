# SOLUTION — tenant-document-acl

## Root cause
`get_document` skips tenant ownership check (IDOR).

## Investigation path
Failing cross-tenant tests → service.py.

## Reference implementation
```python
if doc is None or doc.tenant_id != principal.tenant_id:
    raise HTTPException(404, "document not found")
```

## Wrong alternatives
200 empty body; list-only checks.

## AI failure modes
1. Existence-then-403 oracle.
2. Forget write path (shared helper helps).

## Edge cases
PATCH blocked; 401 without bearer.

## Verification
`pytest -q`

## Complexity
Medium, 25–30 min.

## Expected Event Timeline
| t | Event |
|---|---|
| 0–5 | Reproduce |
| 5–15 | Tenant check |
| 15–25 | PATCH verify |
| 25–30 | Done |

## Positive signals
Uniform 404.

## Negative signals
CDN-only.

## Recovery signals
Settles on 404.

## Interviewer Observations
Existence leakage.

## Rubric (100)
| ID | Criterion | Pts |
|---|---|---|
| A | Diagnosis | 25 |
| B | Block GET | 20 |
| C | Block PATCH | 15 |
| D | No leak | 15 |
| E | Tests | 15 |
| F | Scope | 5 |
| G | Authz | 5 |

## Derived Timeline Metrics
Reproduce <8m; fix <25m.

## Defend-Your-Code (4)
1. Q: 403 vs 404? A: Ticket prefers 404.
2. Q: DB key enough? A: Enforce in service.
3. Q: List enough? A: Direct id bypasses.
4. Q: CDN? A: Origin returns body.
