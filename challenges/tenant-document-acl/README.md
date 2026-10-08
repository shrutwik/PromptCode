# Document access

You are on documents. Someone at Acme opened `/documents/doc_globex_1` and received Globex’s title and body. They should not learn that the file exists.

Acme and Globex are two tenants. Each request carries a bearer token that maps to a user and a tenant.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

GET and PATCH for a document id from another tenant respond 404. The body does not include that tenant’s title or text. A missing id is also 404.

Acme can still GET its own documents, and the list route still returns only the caller’s tenant. Globex can still read Globex documents. A missing or unknown token is 401.

People will blame a CDN cache. That is a hypothesis.

## Getting started

```bash
pip install -r requirements.txt
pytest -q
```

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: Authorization scopes resource lookup and writes; hiding response fields is insufficient.

### Part 1 — Identify scope and failures

Distinguish missing authentication, missing resources and a resource outside the caller’s tenant without disclosing private content.

Evidence to show:

- No authentication yields 401; missing or out-of-scope resources yield 404 without private content.

### Part 2 — Apply policy end to end

Keep authorized list/read/edit flows working in both tenants and preserve untouched document fields.

Evidence to show:

- Authorized reads/edits succeed in both tenants and leave unrelated fields and documents intact.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- Denied foreign requests must not poison later authorized writes or unrelated data.

### Part 4 — Changed requirement — optional discussion

Introduce explicit cross-tenant sharing grants. Specify owner and recipient rights, revocation and default denial before extending lookup policy; a grant must not authorize unrelated documents.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
