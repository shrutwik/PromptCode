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
