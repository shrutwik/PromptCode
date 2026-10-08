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

## Parts and reviewer evidence

Authorization scopes resource lookup and writes; hiding response fields is insufficient.

- Part 1 (Identify scope and failures): unauthenticated, missing-id.
- Part 2 (Apply policy end to end): own-list-and-get, other-tenant-own, own-patch.
- Part 3 (Pressure-test the model): cross-tenant-get, cross-tenant-patch, reverse-tenant-isolation, unauthenticated-mutations, interleaved-scoped-writes.

Part 3 checks this contract property: Denied foreign requests must not poison later authorized writes or unrelated data. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: A resource authorized for one principal can be reused without rechecking the next principal. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: Introduce explicit cross-tenant sharing grants. Specify owner and recipient rights, revocation and default denial before extending lookup policy; a grant must not authorize unrelated documents. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: 403 vs 404? A: Ticket prefers 404.
2. Q: DB key enough? A: Enforce in service.
3. Q: List enough? A: Direct id bypasses.
4. Q: CDN? A: Origin returns body.

## Deeper assessment insight

Authorization constrains resource lookup and mutation; errors must not reveal a foreign resource.

Check both tenant directions and both GET/PATCH paths. Compare rejected response and stored fields, then demonstrate authorized edits still work.

Plausible wrong repair: Hiding sensitive fields in GET while allowing PATCH still permits another tenant to mutate the document. Ask the candidate for a concrete failing example, not just an assertion that the shortcut is bad.

Changed requirement: Discuss sharing access between tenants with an explicit grant model; it does not permit removing baseline tenant isolation. Keep this separate from baseline scoring and record the candidate reasoning and verification evidence.
