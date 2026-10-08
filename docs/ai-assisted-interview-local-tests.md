# Complete local question and test appendix

> Historical research/ranking snapshot before the October 7 expansion. For the implemented twenty-question library and verified coverage, see [the implementation report](interview-library-expansion.md).

Snapshot: October 7, 2026. These are the ten PromptCode exercises, not recovered employer repositories. Candidate starter defects are intentional. Test code below is reproduced from the local workspace; no challenge implementation has been changed or executed by this research pass.

Inventory: **12 visible test files**, **65 named test definitions**, **62 trusted behavioral probes**, plus the ACL fixture file. Parameterized definitions can execute more than once; named definitions are not run counts.

## How to read the evaluator material

Trusted inventory version: `behavioral-2026-10-v2`. The server compares each probe observation to its independent expected JSON result. Each case runs in a fresh candidate container, so state should not leak between cases. A case weight is a scoring weight, not a count of assertions. Full expected arrays are preserved below; transition-matrix cases cover more than one transition. Source and behavior-review gaps are explicit: a full behavioral score does not prove UI rendering, calibrated latency, counter integrity or refactoring direction. See the [evaluator documentation](/Users/shrutwik/Desktop/PromptCode/backend/app/services/interview/trusted_cases/README.md).

Expected output and grading probes are interviewer material: do not bundle this appendix into a candidate-only challenge delivery.

| Exercise | Named visible tests | Trusted cases | Weight sum | Manual review |
|---|---:|---:|---:|---|
| 21. tenant-document-acl | 7 | 9 | 23 | No extra manual requirement registered |
| 22. webhook-delivery-retry | 5 | 6 | 18 | No extra manual requirement registered |
| 23. invoice-status-transition | 8 | 6 | 17 | No extra manual requirement registered |
| 24. subscription-proration-boundary | 7 | 7 | 17 | No extra manual requirement registered |
| 25. shipment-csv-merge | 6 | 6 | 15 | No extra manual requirement registered |
| 26. notification-feed-stale | 5 | 6 | 14 | React rendered badge matches store |
| 27. order-hold-reason | 6 | 6 | 14 | No extra manual requirement registered |
| 28. workspace-label-propagation | 7 | 5 | 14 | React screen displays persisted labels |
| 29. catalog-suggest-latency | 7 | 5 | 14 | 200ms latency under calibrated load; scan instrumentation cannot be self-attested |
| 30. pricing-rule-extract | 7 | 6 | 15 | quote delegates to extracted applyRules; source review |

## 21. tenant-document-acl

[Candidate README](/Users/shrutwik/Desktop/PromptCode/challenges/tenant-document-acl/README.md) · Trusted inventory digest: `d6e84d8e82831886e2e63b728f146450f3700d63269559a62920f3a35d28ac04`

### Exact candidate instructions

````text
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
````

### Exact visible test source and fixtures

#### conftest.py

[Source](/Users/shrutwik/Desktop/PromptCode/challenges/tenant-document-acl/tests/conftest.py) · SHA-256 `7d0f0cfff1f69cf7fe9c941dabb75817fba459fb8ca145154d6af928b1665023`

Named tests: Fixture/support module; no test definitions.

```python
import pytest
from app import db
from app.models import Document
@pytest.fixture(autouse=True)
def seed_docs():
    db.reset()
    db.seed(Document("doc_acme_1", "tenant_acme", "Acme Plan", "secret-acme"))
    db.seed(Document("doc_globex_1", "tenant_globex", "Globex Plan", "secret-globex"))
```

#### test_acl.py

[Source](/Users/shrutwik/Desktop/PromptCode/challenges/tenant-document-acl/tests/test_acl.py) · SHA-256 `b00dca41d73041ccfdab5b4bfef3341a6ee5e5a791f0e91c5fdb8149c02c6699`

Named tests: `test_cross_tenant_update_preserves_all_fields`, `test_unauthenticated_update_preserves_document`, `test_list_is_tenant_scoped`, `test_owner_can_read_own_doc`, `test_missing_doc_is_404`, `test_cross_tenant_get_is_404`, `test_cross_tenant_patch_is_404`

```python
from fastapi.testclient import TestClient
import pytest
from app import db
from app.main import app
client = TestClient(app)

@pytest.mark.parametrize('token,foreign_id', [('tok_acme', 'doc_globex_1'), ('tok_globex', 'doc_acme_1')])
def test_cross_tenant_update_preserves_all_fields(token, foreign_id):
    doc = db.get_by_id(foreign_id)
    before = (doc.title, doc.body, doc.tenant_id)
    headers = {'Authorization': f'Bearer {token}'}
    read = client.get(f'/documents/{foreign_id}', headers=headers)
    assert read.status_code == 404
    assert doc.body not in read.text
    update = client.patch(f'/documents/{foreign_id}', headers=headers, json={'title': 'hacked', 'body': 'hacked'})
    assert update.status_code == 404
    saved = db.get_by_id(foreign_id)
    assert (saved.title, saved.body, saved.tenant_id) == before

@pytest.mark.parametrize('headers', [{}, {'Authorization': 'Bearer unknown'}])
def test_unauthenticated_update_preserves_document(headers):
    response = client.patch('/documents/doc_acme_1', headers=headers, json={'body': 'hacked'})
    assert response.status_code == 401
    assert db.get_by_id('doc_acme_1').body == 'secret-acme'
def test_list_is_tenant_scoped():
    res = client.get("/documents", headers={"Authorization": "Bearer tok_acme"})
    assert {d["id"] for d in res.json()} == {"doc_acme_1"}
def test_owner_can_read_own_doc():
    assert client.get("/documents/doc_acme_1", headers={"Authorization": "Bearer tok_acme"}).json()["body"] == "secret-acme"
def test_missing_doc_is_404():
    assert client.get("/documents/nope", headers={"Authorization": "Bearer tok_acme"}).status_code == 404
def test_cross_tenant_get_is_404():
    res = client.get("/documents/doc_globex_1", headers={"Authorization": "Bearer tok_acme"})
    assert res.status_code == 404
    assert "secret-globex" not in res.text
def test_cross_tenant_patch_is_404():
    assert client.patch("/documents/doc_globex_1", headers={"Authorization": "Bearer tok_acme"}, json={"title": "hacked"}).status_code == 404
```

### Exact trusted behavioral probes

#### cross-tenant-get — weight 4

Probe (observation adapter body, not a standalone program):

```python
from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.models import Document
db.reset()
db.seed(Document('ours','tenant_acme','Acme','own'))
db.seed(Document('foreign','tenant_globex','SECRET TITLE','SECRET BODY'))
c=TestClient(app)
h={'Authorization':'Bearer tok_acme'}
r=c.get('/documents/foreign',headers=h)
result=[r.status_code,'SECRET' in r.text]
```

Expected JSON:

```json
[
  404,
  false
]
```

#### cross-tenant-patch — weight 4

Probe (observation adapter body, not a standalone program):

```python
from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.models import Document
db.reset()
db.seed(Document('ours','tenant_acme','Acme','own'))
db.seed(Document('foreign','tenant_globex','SECRET TITLE','SECRET BODY'))
c=TestClient(app)
h={'Authorization':'Bearer tok_acme'}
r=c.patch('/documents/foreign',headers=h,json={'body':'attacked'})
result=[r.status_code,db.get_by_id('foreign').body]
```

Expected JSON:

```json
[
  404,
  "SECRET BODY"
]
```

#### own-list-and-get — weight 2

Probe (observation adapter body, not a standalone program):

```python
from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.models import Document
db.reset()
db.seed(Document('ours','tenant_acme','Acme','own'))
db.seed(Document('foreign','tenant_globex','SECRET TITLE','SECRET BODY'))
c=TestClient(app)
h={'Authorization':'Bearer tok_acme'}
result=[c.get('/documents/ours',headers=h).status_code,[r['id'] for r in c.get('/documents',headers=h).json()]]
```

Expected JSON:

```json
[
  200,
  [
    "ours"
  ]
]
```

#### unauthenticated — weight 2

Probe (observation adapter body, not a standalone program):

```python
from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.models import Document
db.reset()
db.seed(Document('ours','tenant_acme','Acme','own'))
db.seed(Document('foreign','tenant_globex','SECRET TITLE','SECRET BODY'))
c=TestClient(app)
h={'Authorization':'Bearer tok_acme'}
result=[c.get('/documents').status_code,c.get('/documents',headers={'Authorization':'Bearer unknown'}).status_code]
```

Expected JSON:

```json
[
  401,
  401
]
```

#### other-tenant-own — weight 1

Probe (observation adapter body, not a standalone program):

```python
from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.models import Document
db.reset()
db.seed(Document('ours','tenant_acme','Acme','own'))
db.seed(Document('foreign','tenant_globex','SECRET TITLE','SECRET BODY'))
c=TestClient(app)
h={'Authorization':'Bearer tok_acme'}
result=c.get('/documents/foreign',headers={'Authorization':'Bearer tok_globex'}).status_code
```

Expected JSON:

```json
200
```

#### own-patch — weight 2

Probe (observation adapter body, not a standalone program):

```python
from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.models import Document
db.reset()
db.seed(Document('ours','tenant_acme','Acme','own'))
db.seed(Document('foreign','tenant_globex','SECRET TITLE','SECRET BODY'))
c=TestClient(app)
h={'Authorization':'Bearer tok_acme'}
r=c.patch('/documents/ours',headers=h,json={'body':'updated own'})
result=[r.status_code,c.get('/documents/ours',headers=h).json().get('body')]
```

Expected JSON:

```json
[
  200,
  "updated own"
]
```

#### missing-id — weight 1

Probe (observation adapter body, not a standalone program):

```python
from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.models import Document
db.reset()
db.seed(Document('ours','tenant_acme','Acme','own'))
db.seed(Document('foreign','tenant_globex','SECRET TITLE','SECRET BODY'))
c=TestClient(app)
h={'Authorization':'Bearer tok_acme'}
result=c.get('/documents/missing',headers=h).status_code
```

Expected JSON:

```json
404
```

#### reverse-tenant-isolation — weight 4

Probe (observation adapter body, not a standalone program):

```python
from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.models import Document
db.reset()
db.seed(Document('ours','tenant_acme','Acme','own'))
db.seed(Document('foreign','tenant_globex','SECRET TITLE','SECRET BODY'))
c=TestClient(app)
h={'Authorization':'Bearer tok_acme'}
other={'Authorization':'Bearer tok_globex'}
r=c.patch('/documents/ours',headers=other,json={'title':'attacked','body':'attacked'})
result=[c.get('/documents/ours',headers=other).status_code,r.status_code,db.get_by_id('ours').title,db.get_by_id('ours').body,[d['id'] for d in c.get('/documents',headers=other).json()]]
```

Expected JSON:

```json
[
  404,
  404,
  "Acme",
  "own",
  [
    "foreign"
  ]
]
```

#### unauthenticated-mutations — weight 3

Probe (observation adapter body, not a standalone program):

```python
from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.models import Document
db.reset()
db.seed(Document('ours','tenant_acme','Acme','own'))
db.seed(Document('foreign','tenant_globex','SECRET TITLE','SECRET BODY'))
c=TestClient(app)
h={'Authorization':'Bearer tok_acme'}
result=[c.patch('/documents/ours',json={'body':'attacked'}).status_code,c.patch('/documents/ours',headers={'Authorization':'Bearer unknown'},json={'title':'attacked'}).status_code,db.get_by_id('ours').title,db.get_by_id('ours').body]
```

Expected JSON:

```json
[
  401,
  401,
  "Acme",
  "own"
]
```

### Remaining review requirement

No additional manual gap is registered in this snapshot. That does not prove exhaustive correctness beyond the supplied contracts and fixtures.

## 22. webhook-delivery-retry

[Candidate README](/Users/shrutwik/Desktop/PromptCode/challenges/webhook-delivery-retry/README.md) · Trusted inventory digest: `5ebee11e39ae2f7b06051f802f5b34fd8b23ec7f2e19a434987580a17130164a`

### Exact candidate instructions

````text
# Webhook retry

You are on outbound webhooks. Receivers sometimes answer 500, and the worker retries. Finance then sees the charge recorded twice for one delivery. A flush of the pending queue also made staging fall over.

Delivery is at-least-once. A retry after a 5xx is normal. The side effect has to survive that.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

A delivery that fails and then succeeds still records the charge once for that delivery id. Attempts stop at the retry policy’s max.

Flushing a batch keeps at most about five posts in flight at once.

Lowering the timeout is a hypothesis. The duplicate charge is the incident.

## Getting started

```bash
npm install
npm test
```
````

### Exact visible test source and fixtures

#### worker.test.ts

[Source](/Users/shrutwik/Desktop/PromptCode/challenges/webhook-delivery-retry/tests/worker.test.ts) · SHA-256 `db076386526f7037a057bb9b9a31f970d9825b803fa8d823414eab82173cf8ae`

Named tests: `caps failed attempts and charges an exhausted delivery only once`, `preserves mixed batch result order and handles an empty batch`, `eventually succeeds after transient failures`, `does not charge more than once per successful delivery id`, `bounds concurrent outbound posts when delivering a batch`

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { deliverOne, deliverAll, resetConcurrencyStats, wrapClientWithStats, getMaxInFlight } from '../src/worker.js';
import { flakyClient } from '../src/httpMock.js';
import { resetCharges, chargeCount } from '../src/sideEffects.js';
import type { DeliveryJob } from '../src/types.js';
function job(id: string): DeliveryJob { return { id, url: `https://example.test/${id}`, payload: { id }, attempts: 0 }; }
beforeEach(() => { resetCharges(); resetConcurrencyStats(); });
describe('deliverOne', () => {
  it('caps failed attempts and charges an exhausted delivery only once', async () => {
    let calls = 0;
    const client = { post: async () => { calls++; return { ok: false, status: 500 }; } };
    expect(await deliverOne(job('failed'), client, { maxAttempts: 4, backoffMs: 0 })).toBe(false);
    expect(calls).toBe(4);
    expect(chargeCount('failed')).toBe(1);
  });
  it('preserves mixed batch result order and handles an empty batch', async () => {
    const jobs = Array.from({ length: 12 }, (_, i) => job(String(i)));
    const client = { post: async (url: string) => {
      const ok = Number(url.split('/').pop()) % 2 === 0;
      return { ok, status: ok ? 200 : 500 };
    } };
    expect(await deliverAll(jobs, client, { maxAttempts: 2, backoffMs: 0 })).toEqual(jobs.map((_, i) => i % 2 === 0));
    expect(chargeCount()).toBe(12);
    expect(await deliverAll([], client, { maxAttempts: 2, backoffMs: 0 })).toEqual([]);
  });
  it('eventually succeeds after transient failures', async () => {
    const client = flakyClient(new Map([['d1', 2]]));
    expect(await deliverOne(job('d1'), client, { maxAttempts: 3, backoffMs: 0 })).toBe(true);
  });
});
describe('idempotency and concurrency', () => {
  it('does not charge more than once per successful delivery id', async () => {
    const client = flakyClient(new Map([['d2', 2]]));
    await deliverOne(job('d2'), client, { maxAttempts: 3, backoffMs: 0 });
    expect(chargeCount('d2')).toBe(1);
  });
  it('bounds concurrent outbound posts when delivering a batch', async () => {
    const fail = new Map<string, number>();
    const jobs = Array.from({ length: 20 }, (_, i) => { fail.set(`j${i}`, 0); return job(`j${i}`); });
    const client = wrapClientWithStats(flakyClient(fail));
    await deliverAll(jobs, client, { maxAttempts: 1, backoffMs: 0 });
    expect(getMaxInFlight()).toBeLessThanOrEqual(5);
  });
});
```

### Exact trusted behavioral probes

#### retry-charge-once — weight 4

Probe (observation adapter body, not a standalone program):

```typescript
import {deliverOne,deliverAll} from './src/worker';import {chargeCount,resetCharges} from './src/sideEffects';resetCharges();let calls=0;const client={post:async()=>({ok:++calls===3,status:calls===3?200:500})};const ok=await deliverOne({id:'job',url:'http://receiver',payload:{},attempts:0},client,{maxAttempts:3,backoffMs:0});return [ok,calls,chargeCount('job')];
```

Expected JSON:

```json
[
  true,
  3,
  1
]
```

#### repeat-delivery-idempotent — weight 2

Probe (observation adapter body, not a standalone program):

```typescript
import {deliverOne,deliverAll} from './src/worker';import {chargeCount,resetCharges} from './src/sideEffects';resetCharges();const job={id:'same',url:'http://receiver',payload:{},attempts:0};const client={post:async()=>({ok:true,status:200})};await deliverOne(job,client,{maxAttempts:1,backoffMs:0});await deliverOne(job,client,{maxAttempts:1,backoffMs:0});return chargeCount('same');
```

Expected JSON:

```json
1
```

#### attempts-bounded — weight 3

Probe (observation adapter body, not a standalone program):

```typescript
import {deliverOne,deliverAll} from './src/worker';import {chargeCount,resetCharges} from './src/sideEffects';resetCharges();let calls=0;const ok=await deliverOne({id:'job',url:'http://receiver',payload:{},attempts:0},{post:async()=>{calls++;return {ok:false,status:500}}},{maxAttempts:2,backoffMs:0});return [ok,calls];
```

Expected JSON:

```json
[
  false,
  2
]
```

#### flush-concurrency — weight 3

Probe (observation adapter body, not a standalone program):

```typescript
import {deliverOne,deliverAll} from './src/worker';import {chargeCount,resetCharges} from './src/sideEffects';resetCharges();let active=0,max=0;const client={post:async()=>{active++;max=Math.max(max,active);await new Promise(r=>setTimeout(r,5));active--;return {ok:true,status:200}}};const jobs=Array.from({length:19},(_,i)=>({id:'j'+i,url:'http://receiver',payload:{},attempts:0}));const results=await deliverAll(jobs,client,{maxAttempts:1,backoffMs:0});return [results.every(Boolean),max<=5,chargeCount()];
```

Expected JSON:

```json
[
  true,
  true,
  19
]
```

#### exhausted-retries-charge-once — weight 3

Probe (observation adapter body, not a standalone program):

```typescript
import {deliverOne,deliverAll} from './src/worker';import {chargeCount,resetCharges} from './src/sideEffects';resetCharges();let calls=0;const ok=await deliverOne({id:'failed',url:'http://receiver',payload:{},attempts:0},{post:async()=>{calls++;return {ok:false,status:500}}},{maxAttempts:4,backoffMs:0});return [ok,calls,chargeCount('failed')];
```

Expected JSON:

```json
[
  false,
  4,
  1
]
```

#### mixed-batch-result-order — weight 3

Probe (observation adapter body, not a standalone program):

```typescript
import {deliverOne,deliverAll} from './src/worker';import {chargeCount,resetCharges} from './src/sideEffects';resetCharges();const jobs=Array.from({length:12},(_,i)=>({id:'j'+i,url:'http://receiver/'+i,payload:{},attempts:0}));const client={post:async(url)=>{const ok=Number(url.split('/').pop())%2===0;return {ok,status:ok?200:500};}};const results=await deliverAll(jobs,client,{maxAttempts:2,backoffMs:0});return [results,chargeCount(),await deliverAll([],client,{maxAttempts:2,backoffMs:0})];
```

Expected JSON:

```json
[
  [
    true,
    false,
    true,
    false,
    true,
    false,
    true,
    false,
    true,
    false,
    true,
    false
  ],
  12,
  []
]
```

### Remaining review requirement

No additional manual gap is registered in this snapshot. That does not prove exhaustive correctness beyond the supplied contracts and fixtures.

## 23. invoice-status-transition

[Candidate README](/Users/shrutwik/Desktop/PromptCode/challenges/invoice-status-transition/README.md) · Trusted inventory digest: `94e6c1bb7e55928cc2cf6079cc0360e108ad74adf3b0ec9e68e853ffeedab21b`

### Exact candidate instructions

````text
# Invoice status

You are the billing engineer on call before month-end close.

Finance collected invoice `inv_paid`, then this service showed it as draft. Draft is the editable state. A paid invoice that looks like a draft can change after money has moved.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

A paid invoice stays paid unless it is voided. Void keeps the paper trail.

These moves still succeed: draft to sent, draft to void, sent to paid, sent to void, and paid to void. Void is terminal. A status moved onto itself is not a transition.

`POST /invoices/:id/transition` returns 409 when the move is illegal, including sent back to draft, and the stored status stays as it was. A missing invoice is a different failure from an illegal move.

Statuses are `draft`, `sent`, `paid`, and `void`. Amounts are integer cents.

A teammate says last sprint’s date formatter rewrote the status. That is a hypothesis.

## Getting started

```bash
npm install
npm test
```
````

### Exact visible test source and fixtures

#### statusMachine.test.ts

[Source](/Users/shrutwik/Desktop/PromptCode/challenges/invoice-status-transition/tests/statusMachine.test.ts) · SHA-256 `509e10b5ccecdbd26dbc14dd8624785c1f35789e60cc8d4cac7dddc9eea86c13`

Named tests: `refused API changes preserve the invoice including money`, `missing status is a validation error with no mutation`, `draft can go to sent`, `sent can go to paid`, `paid can go to void`, `void has no targets`, `API returns 409 for sent -> draft`, `rejects paid -> draft`

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { canTransition, allowedTargets } from '../src/statusMachine.js';
import { transitionInvoice } from '../src/invoiceService.js';
import { resetStore, seedInvoice, getInvoice } from '../src/store.js';
import { handleRequest } from '../src/api.js';
beforeEach(() => {
  resetStore();
  seedInvoice({ id: 'inv_1', customerId: 'cus_1', amountCents: 5000, status: 'draft', issuedAt: '2024-06-01T15:00:00.000Z', updatedAt: '2024-06-01T15:00:00.000Z' });
  seedInvoice({ id: 'inv_paid', customerId: 'cus_1', amountCents: 1200, status: 'paid', issuedAt: '2024-05-01T12:00:00.000Z', updatedAt: '2024-05-02T12:00:00.000Z' });
});
describe('allowed transitions', () => {
  it('refused API changes preserve the invoice including money', () => {
    const before = { ...getInvoice('inv_paid')! };
    expect(handleRequest({ method: 'POST', path: '/invoices/inv_paid/transition', body: { status: 'draft' } }).status).toBe(409);
    expect(getInvoice('inv_paid')).toEqual(before);
  });
  it('missing status is a validation error with no mutation', () => {
    const before = { ...getInvoice('inv_1')! };
    expect(handleRequest({ method: 'POST', path: '/invoices/inv_1/transition', body: {} }).status).toBe(400);
    expect(getInvoice('inv_1')).toEqual(before);
  });
  it('draft can go to sent', () => { expect(canTransition('draft', 'sent')).toBe(true); expect(transitionInvoice('inv_1', 'sent').status).toBe('sent'); });
  it('sent can go to paid', () => { transitionInvoice('inv_1', 'sent'); expect(transitionInvoice('inv_1', 'paid').status).toBe('paid'); });
  it('paid can go to void', () => { expect(transitionInvoice('inv_paid', 'void').status).toBe('void'); });
  it('void has no targets', () => { expect(allowedTargets('void')).toEqual([]); });
  it('API returns 409 for sent -> draft', () => {
    transitionInvoice('inv_1', 'sent');
    expect(handleRequest({ method: 'POST', path: '/invoices/inv_1/transition', body: { status: 'draft' } }).status).toBe(409);
  });
  it('rejects paid -> draft', () => {
    expect(canTransition('paid', 'draft')).toBe(false);
    expect(() => transitionInvoice('inv_paid', 'draft')).toThrow(/Illegal transition/);
  });
});
```

### Exact trusted behavioral probes

#### legal-graph — weight 4

Probe (observation adapter body, not a standalone program):

```typescript
import {canTransition} from './src/statusMachine'; import {handleRequest} from './src/api'; import {resetStore,seedInvoice,getInvoice} from './src/store';return ['draft','sent','paid','void'].flatMap(a=>['draft','sent','paid','void'].map(b=>canTransition(a,b)));
```

Expected JSON:

```json
[
  false,
  true,
  false,
  true,
  false,
  false,
  true,
  true,
  false,
  false,
  false,
  true,
  false,
  false,
  false,
  false
]
```

#### illegal-preserves-paid — weight 4

Probe (observation adapter body, not a standalone program):

```typescript
import {canTransition} from './src/statusMachine'; import {handleRequest} from './src/api'; import {resetStore,seedInvoice,getInvoice} from './src/store';resetStore();seedInvoice({id:'probe',status:'paid',amountCents:197,issuedAt:'2026-01-01',updatedAt:'2026-01-01'});return [handleRequest({method:'POST',path:'/invoices/probe/transition',body:{status:'draft'}}).status,getInvoice('probe').status];
```

Expected JSON:

```json
[
  409,
  "paid"
]
```

#### legal-api-transition — weight 2

Probe (observation adapter body, not a standalone program):

```typescript
import {canTransition} from './src/statusMachine'; import {handleRequest} from './src/api'; import {resetStore,seedInvoice,getInvoice} from './src/store';resetStore();seedInvoice({id:'probe',status:'sent',amountCents:197,issuedAt:'2026-01-01',updatedAt:'2026-01-01'});const r=handleRequest({method:'POST',path:'/invoices/probe/transition',body:{status:'paid'}});return [r.status,getInvoice('probe').status,getInvoice('probe').amountCents];
```

Expected JSON:

```json
[
  200,
  "paid",
  197
]
```

#### missing-distinct — weight 1

Probe (observation adapter body, not a standalone program):

```typescript
import {canTransition} from './src/statusMachine'; import {handleRequest} from './src/api'; import {resetStore,seedInvoice,getInvoice} from './src/store';resetStore();return handleRequest({method:'POST',path:'/invoices/missing/transition',body:{status:'sent'}}).status;
```

Expected JSON:

```json
404
```

#### api-transition-matrix — weight 4

Probe (observation adapter body, not a standalone program):

```typescript
import {canTransition} from './src/statusMachine'; import {handleRequest} from './src/api'; import {resetStore,seedInvoice,getInvoice} from './src/store';return ['draft','sent','paid','void'].flatMap(a=>['draft','sent','paid','void'].map(b=>{resetStore();seedInvoice({id:'matrix',status:a,amountCents:731,issuedAt:'2026-01-01',updatedAt:'2026-01-01'});const r=handleRequest({method:'POST',path:'/invoices/matrix/transition',body:{status:b}});const saved=getInvoice('matrix');return [r.status,saved.status,saved.amountCents];}));
```

Expected JSON:

```json
[
  [
    409,
    "draft",
    731
  ],
  [
    200,
    "sent",
    731
  ],
  [
    409,
    "draft",
    731
  ],
  [
    200,
    "void",
    731
  ],
  [
    409,
    "sent",
    731
  ],
  [
    409,
    "sent",
    731
  ],
  [
    200,
    "paid",
    731
  ],
  [
    200,
    "void",
    731
  ],
  [
    409,
    "paid",
    731
  ],
  [
    409,
    "paid",
    731
  ],
  [
    409,
    "paid",
    731
  ],
  [
    200,
    "void",
    731
  ],
  [
    409,
    "void",
    731
  ],
  [
    409,
    "void",
    731
  ],
  [
    409,
    "void",
    731
  ],
  [
    409,
    "void",
    731
  ]
]
```

#### missing-status-preserves-state — weight 2

Probe (observation adapter body, not a standalone program):

```typescript
import {canTransition} from './src/statusMachine'; import {handleRequest} from './src/api'; import {resetStore,seedInvoice,getInvoice} from './src/store';resetStore();seedInvoice({id:'probe',status:'sent',amountCents:731,issuedAt:'2026-01-01',updatedAt:'2026-01-01'});return [handleRequest({method:'POST',path:'/invoices/probe/transition',body:{}}).status,getInvoice('probe').status];
```

Expected JSON:

```json
[
  400,
  "sent"
]
```

### Remaining review requirement

No additional manual gap is registered in this snapshot. That does not prove exhaustive correctness beyond the supplied contracts and fixtures.

## 24. subscription-proration-boundary

[Candidate README](/Users/shrutwik/Desktop/PromptCode/challenges/subscription-proration-boundary/README.md) · Trusted inventory digest: `35da89ca4ba4f485046fe6fe70a1603df2270f94fac8fdda6ef184b24d8ab6db`

### Exact candidate instructions

````text
# Period boundary

You are on subscriptions. A customer canceled exactly when the billing period rolled, and the books treated that instant as still inside the period.

Support thinks the Chicago clock display is wrong again. The credit is computed from the stored period and the cancel instant. The display helper only formats that instant.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

The instant at period end is outside the period and credits nothing. The instant at period start is inside. A cancel in the middle of the period still gets a credit. A cancel before the period credits nothing.

The tests that already describe those cases stay as they are. Leave them alone and make the boundary agree with them.

## Getting started

```bash
pip install -r requirements.txt
pytest -q
```
````

### Exact visible test source and fixtures

#### test_proration.py

[Source](/Users/shrutwik/Desktop/PromptCode/challenges/subscription-proration-boundary/tests/test_proration.py) · SHA-256 `df26baf63580742ba7f280e1b5f3039c6369fd8be7e91d8becaa656b6d2fa705`

Named tests: `test_mid_period_cancel_gets_credit`, `test_cancel_before_period_no_credit`, `test_contains_start_inclusive`, `test_cancel_exactly_at_period_end_no_credit`, `test_display_helper_smoke`, `test_adjacent_periods_have_one_owner_at_timezone_equivalent_boundary`, `test_microsecond_boundaries`

```python
from datetime import datetime, timezone
from proration.period import Period, contains, period_from_iso
from proration.billing import Subscription, proration_credit

def test_mid_period_cancel_gets_credit():
    period = period_from_iso("2024-01-01T00:00:00Z", "2024-02-01T00:00:00Z")
    sub = Subscription("s1", 3100, period)
    assert proration_credit(sub, "2024-01-16T00:00:00Z") == 1600

def test_cancel_before_period_no_credit():
    period = period_from_iso("2024-01-01T00:00:00Z", "2024-02-01T00:00:00Z")
    sub = Subscription("s1", 3100, period)
    assert proration_credit(sub, "2023-12-31T23:00:00Z") == 0

def test_contains_start_inclusive():
    period = period_from_iso("2024-01-01T00:00:00Z", "2024-02-01T00:00:00Z")
    assert contains(period, datetime(2024, 1, 1, tzinfo=timezone.utc)) is True

def test_cancel_exactly_at_period_end_no_credit():
    period = period_from_iso("2024-01-01T00:00:00Z", "2024-02-01T00:00:00Z")
    sub = Subscription("s1", 3100, period)
    assert contains(period, period.end) is False
    assert proration_credit(sub, "2024-02-01T00:00:00Z") == 0

def test_display_helper_smoke():
    from proration.timeutil import format_display, parse_utc
    assert "2024" in format_display(parse_utc("2024-01-01T06:00:00Z"))

def test_adjacent_periods_have_one_owner_at_timezone_equivalent_boundary():
    from proration.timeutil import parse_utc
    previous = period_from_iso('2026-01-01T00:00:00Z', '2026-02-01T00:00:00Z')
    following = period_from_iso('2026-02-01T00:00:00Z', '2026-03-01T00:00:00Z')
    instant = parse_utc('2026-02-01T01:00:00+01:00')
    assert not contains(previous, instant)
    assert contains(following, instant)
    assert proration_credit(Subscription('next', 2800, following), '2026-02-01T01:00:00+01:00') == 2800

def test_microsecond_boundaries():
    from proration.timeutil import parse_utc
    period = period_from_iso('2026-01-01T00:00:00Z', '2026-02-01T00:00:00Z')
    assert contains(period, parse_utc('2026-01-31T23:59:59.999999Z'))
    assert not contains(period, parse_utc('2026-02-01T00:00:00.000001Z'))
    assert not contains(period, parse_utc('2025-12-31T23:59:59.999999Z'))
```

### Exact trusted behavioral probes

#### end-excluded — weight 4

Probe (observation adapter body, not a standalone program):

```python
from proration.period import period_from_iso,contains
from proration.timeutil import parse_utc
from proration.billing import Subscription,proration_credit
p=period_from_iso('2026-01-01T00:00:00Z','2026-02-01T00:00:00Z')
s=Subscription('probe',3100,p)
result=[contains(p,p.end),proration_credit(s,'2026-02-01T00:00:00Z')]
```

Expected JSON:

```json
[
  false,
  0
]
```

#### start-included — weight 2

Probe (observation adapter body, not a standalone program):

```python
from proration.period import period_from_iso,contains
from proration.timeutil import parse_utc
from proration.billing import Subscription,proration_credit
p=period_from_iso('2026-01-01T00:00:00Z','2026-02-01T00:00:00Z')
s=Subscription('probe',3100,p)
result=[contains(p,p.start),proration_credit(s,'2026-01-01T00:00:00Z')]
```

Expected JSON:

```json
[
  true,
  3100
]
```

#### mid-period-credit — weight 2

Probe (observation adapter body, not a standalone program):

```python
from proration.period import period_from_iso,contains
from proration.timeutil import parse_utc
from proration.billing import Subscription,proration_credit
p=period_from_iso('2026-01-01T00:00:00Z','2026-02-01T00:00:00Z')
s=Subscription('probe',3100,p)
result=proration_credit(s,'2026-01-16T00:00:00Z')
```

Expected JSON:

```json
1600
```

#### before-period — weight 2

Probe (observation adapter body, not a standalone program):

```python
from proration.period import period_from_iso,contains
from proration.timeutil import parse_utc
from proration.billing import Subscription,proration_credit
p=period_from_iso('2026-01-01T00:00:00Z','2026-02-01T00:00:00Z')
s=Subscription('probe',3100,p)
result=proration_credit(s,'2025-12-31T23:59:59Z')
```

Expected JSON:

```json
0
```

#### timezone-equivalence — weight 1

Probe (observation adapter body, not a standalone program):

```python
from proration.period import period_from_iso,contains
from proration.timeutil import parse_utc
from proration.billing import Subscription,proration_credit
p=period_from_iso('2026-01-01T00:00:00Z','2026-02-01T00:00:00Z')
s=Subscription('probe',3100,p)
result=contains(p,parse_utc('2026-01-31T19:00:00-05:00'))
```

Expected JSON:

```json
false
```

#### adjacent-period-single-membership — weight 3

Probe (observation adapter body, not a standalone program):

```python
from proration.period import period_from_iso,contains
from proration.timeutil import parse_utc
from proration.billing import Subscription,proration_credit
p=period_from_iso('2026-01-01T00:00:00Z','2026-02-01T00:00:00Z')
s=Subscription('probe',3100,p)
next_p=period_from_iso('2026-02-01T00:00:00Z','2026-03-01T00:00:00Z')
instant=parse_utc('2026-02-01T01:00:00+01:00')
result=[contains(p,instant),contains(next_p,instant),proration_credit(Subscription('next',2800,next_p),'2026-02-01T01:00:00+01:00')]
```

Expected JSON:

```json
[
  false,
  true,
  2800
]
```

#### microsecond-boundaries — weight 3

Probe (observation adapter body, not a standalone program):

```python
from proration.period import period_from_iso,contains
from proration.timeutil import parse_utc
from proration.billing import Subscription,proration_credit
p=period_from_iso('2026-01-01T00:00:00Z','2026-02-01T00:00:00Z')
s=Subscription('probe',3100,p)
result=[contains(p,parse_utc('2026-01-31T23:59:59.999999Z')),contains(p,parse_utc('2026-02-01T00:00:00.000001Z')),contains(p,parse_utc('2025-12-31T23:59:59.999999Z')),proration_credit(s,'2026-01-31T23:59:59.999999Z')]
```

Expected JSON:

```json
[
  true,
  false,
  false,
  0
]
```

### Remaining review requirement

No additional manual gap is registered in this snapshot. That does not prove exhaustive correctness beyond the supplied contracts and fixtures.

## 25. shipment-csv-merge

[Candidate README](/Users/shrutwik/Desktop/PromptCode/challenges/shipment-csv-merge/README.md) · Trusted inventory digest: `945c4c64d7dd9b33e98f9f1574c00b73b9b16771709367e7a6f42acbdaa5d4e7`

### Exact candidate instructions

````text
# Shipment CSV

You own the nightly shipment merge. Warehouse drops two CSV files that landed out of order. A shipment timeline showed a later status before an earlier one, and a quantity that should have been counted once was counted twice.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

Events from separate files come out in timestamp order for each shipment. The same `event_id` in two files counts once. Two events with the same status and different ids both stay, in timestamp order.

A teammate thinks a comma inside a CSV field broke the parser. That is a hypothesis.

## Getting started

```bash
pip install -r requirements.txt
pytest -q
```
````

### Exact visible test source and fixtures

#### test_merge.py

[Source](/Users/shrutwik/Desktop/PromptCode/challenges/shipment-csv-merge/tests/test_merge.py) · SHA-256 `acfe4b9565c30e05d954cd7bb49d37f450354d0a82b319bea4d5194ac110f3ff`

Named tests: `test_basic_timeline_order_happy_path`, `test_quantity_single_batch`, `test_duplicate_event_id_across_batches_not_double_counted`, `test_same_status_different_event_ids_kept_in_ts_order`, `test_timestamp_ties_negative_deltas_and_duplicates`, `test_next_merge_replaces_previous_totals`

```python
from shipment_merge.parse import parse_csv
from shipment_merge.summarize import summarize
from shipment_merge.models import ShipmentEvent
from shipment_merge.merge import merge_events, total_quantity
DAY1 = """event_id,shipment_id,status,ts,quantity_delta
e1,s1,created,2024-01-01T10:00:00Z,1
e2,s1,picked,2024-01-01T15:00:00Z,0
"""
DAY2 = """event_id,shipment_id,status,ts,quantity_delta
e3,s1,shipped,2024-01-02T09:00:00Z,0
e4,s1,delivered,2024-01-02T18:00:00Z,0
"""
def test_basic_timeline_order_happy_path():
    assert summarize([parse_csv(DAY1), parse_csv(DAY2)])["timelines"]["s1"] == ["created", "picked", "shipped", "delivered"]
def test_quantity_single_batch():
    events = [ShipmentEvent("a","s2","created","2024-01-01T10:00:00Z",2), ShipmentEvent("b","s2","picked","2024-01-01T11:00:00Z",0)]
    assert summarize([events])["quantities"]["s2"] == 2
def test_duplicate_event_id_across_batches_not_double_counted():
    day1=[ShipmentEvent("e9","s1","created","2024-01-01T23:30:00Z",1)]
    day2=[ShipmentEvent("e9","s1","created","2024-01-01T23:30:00Z",1)]
    assert summarize([day1, day2])["quantities"]["s1"] == 1
def test_same_status_different_event_ids_kept_in_ts_order():
    events=[ShipmentEvent("e1","s1","picked","2024-01-01T10:00:00Z",0), ShipmentEvent("e2","s1","picked","2024-01-01T12:00:00Z",0)]
    assert [e.event_id for e in merge_events([events])] == ["e1","e2"]

def test_timestamp_ties_negative_deltas_and_duplicates():
    a = ShipmentEvent('a', 'ship', 'scan', '2026-01-01', 5)
    b = ShipmentEvent('b', 'ship', 'scan', '2026-01-01', -2)
    assert [e.event_id for e in merge_events([[b, a], [], [a, b, a]])] == ['a', 'b']
    assert total_quantity('ship') == 3

def test_next_merge_replaces_previous_totals():
    merge_events([[ShipmentEvent('old', 'old-ship', 'scan', '2026-01-01', 9)]])
    merge_events([[ShipmentEvent('new', 'new-ship', 'scan', '2026-01-02', 4)]])
    assert total_quantity('old-ship') == 0
    assert total_quantity('new-ship') == 4
    assert merge_events([]) == []
    assert total_quantity('new-ship') == 0
```

### Exact trusted behavioral probes

#### same-status-distinct-id — weight 4

Probe (observation adapter body, not a standalone program):

```python
from shipment_merge.models import ShipmentEvent
from shipment_merge.merge import merge_events,total_quantity
rows=merge_events([[ShipmentEvent('b','ship','scan','2026-01-02',3)],[ShipmentEvent('a','ship','scan','2026-01-01',2)]])
result=[[r.event_id for r in rows],total_quantity('ship')]
```

Expected JSON:

```json
[
  [
    "a",
    "b"
  ],
  5
]
```

#### duplicate-id-once — weight 4

Probe (observation adapter body, not a standalone program):

```python
from shipment_merge.models import ShipmentEvent
from shipment_merge.merge import merge_events,total_quantity
e=ShipmentEvent('unique','ship','packed','2026-01-01',7)
rows=merge_events([[e],[e]])
result=[len(rows),total_quantity('ship')]
```

Expected JSON:

```json
[
  1,
  7
]
```

#### independent-shipments — weight 1

Probe (observation adapter body, not a standalone program):

```python
from shipment_merge.models import ShipmentEvent
from shipment_merge.merge import merge_events,total_quantity
rows=merge_events([[ShipmentEvent('a','s1','x','2026-01-01',2),ShipmentEvent('b','s2','x','2026-01-01',4)]])
result=[total_quantity('s1'),total_quantity('s2')]
```

Expected JSON:

```json
[
  2,
  4
]
```

#### empty-clears-state — weight 1

Probe (observation adapter body, not a standalone program):

```python
from shipment_merge.models import ShipmentEvent
from shipment_merge.merge import merge_events,total_quantity
merge_events([[ShipmentEvent('a','s1','x','2026-01-01',2)]])
result=[merge_events([]),total_quantity('s1')]
```

Expected JSON:

```json
[
  [],
  0
]
```

#### ties-negative-and-multi-file-dedup — weight 3

Probe (observation adapter body, not a standalone program):

```python
from shipment_merge.models import ShipmentEvent
from shipment_merge.merge import merge_events,total_quantity
a=ShipmentEvent('a','ship','scan','2026-01-01',5)
b=ShipmentEvent('b','ship','scan','2026-01-01',-2)
rows=merge_events([[b,a],[],[a,b,a]])
result=[[r.event_id for r in rows],total_quantity('ship')]
```

Expected JSON:

```json
[
  [
    "a",
    "b"
  ],
  3
]
```

#### next-merge-replaces-totals — weight 2

Probe (observation adapter body, not a standalone program):

```python
from shipment_merge.models import ShipmentEvent
from shipment_merge.merge import merge_events,total_quantity
merge_events([[ShipmentEvent('old','old-ship','x','2026-01-01',9)]])
rows=merge_events([[ShipmentEvent('new','new-ship','x','2026-01-02',4)]])
result=[[r.event_id for r in rows],total_quantity('old-ship'),total_quantity('new-ship'),total_quantity('missing')]
```

Expected JSON:

```json
[
  [
    "new"
  ],
  0,
  4,
  0
]
```

### Remaining review requirement

No additional manual gap is registered in this snapshot. That does not prove exhaustive correctness beyond the supplied contracts and fixtures.

## 26. notification-feed-stale

[Candidate README](/Users/shrutwik/Desktop/PromptCode/challenges/notification-feed-stale/README.md) · Trusted inventory digest: `fcff10b0e8edfe3143a5bde57c661f805bbeb8040b35172b3e13d51cd2438232`

### Exact candidate instructions

````text
# Notification feed

You are on the notification feed. A user marks an item read and the unread badge stays. Two quick marks are worse: one of them disappears, and the badge does not match the rows.

Support has a screenshot of a badge that says 2 while the visible rows say read.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

The unread count is how many notifications have `read` set to false. After the feed loads, the badge shows that count.

Marking one item read leaves that row read and drops the badge by one. Marking two items read together leaves both rows read, and the badge matches when both calls finish. A row that was already read stays read.

Someone says the React list key is wrong. That is a hypothesis.

## Getting started

```bash
npm install
npm test
```
````

### Exact visible test source and fixtures

#### feed.test.tsx

[Source](/Users/shrutwik/Desktop/PromptCode/challenges/notification-feed-stale/tests/feed.test.tsx) · SHA-256 `4270be8a758f108770922521bec42b3da6690b5ee0ec03bb04424936452f96bb`

Named tests: `shows unread count`, `marks one read`, `coalesces repeated concurrent marks without losing other updates`, `keeps the snapshot intact when a mark fails`, `marks two without clobber`

```typescript
import React from 'react';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react';
import { NotificationList } from '../src/NotificationList';
import { seedServer } from '../src/api';
import { resetStore, loadFeed, markAsRead, unreadCount, getSnapshot } from '../src/feedStore';
afterEach(() => { cleanup(); });
beforeEach(() => {
  resetStore();
  seedServer([
    { id: 'n1', title: 'Welcome', read: false },
    { id: 'n2', title: 'Invoice', read: false },
    { id: 'n3', title: 'Ship', read: true },
  ]);
});
describe('UI', () => {
  it('shows unread count', async () => {
    render(<NotificationList />);
    await waitFor(() => expect(screen.getByTestId('unread-count').textContent).toBe('2'));
  });
  it('marks one read', async () => {
    render(<NotificationList />);
    await waitFor(() => screen.getByTestId('mark-n1'));
    fireEvent.click(screen.getByTestId('mark-n1'));
    await waitFor(() => expect(screen.getByTestId('unread-count').textContent).toBe('1'));
  });
});
describe('concurrency', () => {
  it('coalesces repeated concurrent marks without losing other updates', async () => {
    await loadFeed();
    await Promise.all(['n1', 'n2', 'n1', 'n3', 'n2'].map(markAsRead));
    expect(unreadCount()).toBe(0);
    expect(getSnapshot().map(n => [n.id, n.read])).toEqual([['n1', true], ['n2', true], ['n3', true]]);
  });
  it('keeps the snapshot intact when a mark fails', async () => {
    await loadFeed();
    const before = JSON.stringify(getSnapshot());
    await expect(markAsRead('missing')).rejects.toThrow('not found');
    expect(JSON.stringify(getSnapshot())).toBe(before);
    expect(unreadCount()).toBe(2);
  });
  it('marks two without clobber', async () => {
    await loadFeed();
    await Promise.all([markAsRead('n1'), markAsRead('n2')]);
    expect(unreadCount()).toBe(0);
    expect(getSnapshot().filter(n => n.id !== 'n3').every(n => n.read)).toBe(true);
  });
});
```

### Exact trusted behavioral probes

#### loaded-count — weight 2

Probe (observation adapter body, not a standalone program):

```typescript
import * as api from './src/api';import * as store from './src/feedStore';store.resetStore();api.seedServer([{id:'a',title:'A',read:false},{id:'b',title:'B',read:false},{id:'c',title:'C',read:true}]);await store.loadFeed();return store.unreadCount();
```

Expected JSON:

```json
2
```

#### one-mark — weight 2

Probe (observation adapter body, not a standalone program):

```typescript
import * as api from './src/api';import * as store from './src/feedStore';store.resetStore();api.seedServer([{id:'a',title:'A',read:false},{id:'b',title:'B',read:false},{id:'c',title:'C',read:true}]);await store.loadFeed();await store.markAsRead('a');return [store.unreadCount(),store.getSnapshot().map(x=>x.read)];
```

Expected JSON:

```json
[
  1,
  [
    true,
    false,
    true
  ]
]
```

#### concurrent-marks — weight 4

Probe (observation adapter body, not a standalone program):

```typescript
import * as api from './src/api';import * as store from './src/feedStore';store.resetStore();api.seedServer([{id:'a',title:'A',read:false},{id:'b',title:'B',read:false},{id:'c',title:'C',read:true}]);await store.loadFeed();await Promise.all([store.markAsRead('a'),store.markAsRead('b')]);return [store.unreadCount(),store.getSnapshot().map(x=>x.read)];
```

Expected JSON:

```json
[
  0,
  [
    true,
    true,
    true
  ]
]
```

#### already-read — weight 1

Probe (observation adapter body, not a standalone program):

```typescript
import * as api from './src/api';import * as store from './src/feedStore';store.resetStore();api.seedServer([{id:'a',title:'A',read:false},{id:'b',title:'B',read:false},{id:'c',title:'C',read:true}]);await store.loadFeed();await store.markAsRead('c');return store.unreadCount();
```

Expected JSON:

```json
2
```

#### duplicate-concurrent-marks — weight 3

Probe (observation adapter body, not a standalone program):

```typescript
import * as api from './src/api';import * as store from './src/feedStore';store.resetStore();api.seedServer([{id:'a',title:'A',read:false},{id:'b',title:'B',read:false},{id:'c',title:'C',read:true}]);await store.loadFeed();await Promise.all(['a','b','a','c','b'].map(id=>store.markAsRead(id)));return [store.unreadCount(),store.getSnapshot().map(x=>[x.id,x.read])];
```

Expected JSON:

```json
[
  0,
  [
    [
      "a",
      true
    ],
    [
      "b",
      true
    ],
    [
      "c",
      true
    ]
  ]
]
```

#### failed-mark-preserves-state — weight 2

Probe (observation adapter body, not a standalone program):

```typescript
import * as api from './src/api';import * as store from './src/feedStore';store.resetStore();api.seedServer([{id:'a',title:'A',read:false},{id:'b',title:'B',read:false},{id:'c',title:'C',read:true}]);await store.loadFeed();const before=JSON.stringify(store.getSnapshot());let rejected=false;try{await store.markAsRead('missing');}catch{rejected=true;}return [rejected,JSON.stringify(store.getSnapshot())===before,store.unreadCount()];
```

Expected JSON:

```json
[
  true,
  true,
  2
]
```

### Remaining review requirement

React rendered badge matches store

## 27. order-hold-reason

[Candidate README](/Users/shrutwik/Desktop/PromptCode/challenges/order-hold-reason/README.md) · Trusted inventory digest: `7f310f06f99fc4e69bcae422baab2ee681521b5ab6746236ba1f27d4bac5b481`

### Exact candidate instructions

````text
# Order hold

You are on the orders API during a warehouse freeze.

Support puts an order on hold with a reason. The next read cannot say why it is held, or the hold does not survive a refresh. Orders created before this field existed are still in the database.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

`POST /orders/:id/hold` with a `hold_reason` stores that reason and returns the order as `on_hold`. The following GET returns the same reason.

`POST /orders/:id/release` returns the order as `open`.

Orders that never had a reason come back with `hold_reason` null. Money is `total_cents`, an integer.

People are blaming the metrics counter. That is a hypothesis.

## Getting started

```bash
pip install -r requirements.txt
pytest -q
```
````

### Exact visible test source and fixtures

#### test_orders.py

[Source](/Users/shrutwik/Desktop/PromptCode/challenges/order-hold-reason/tests/test_orders.py) · SHA-256 `790754c35e787198df339a2c921977cf5b5c33d3be9fde046a39420599337c78`

Named tests: `test_get_legacy_order_shape`, `test_hold_sets_status`, `test_release_clears_hold`, `test_hold_reason_round_trip_and_legacy_null`, `test_replacing_reason_preserves_money_and_other_orders`, `test_optional_reason_and_repeat_release`

```python
from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.models import Order

client = TestClient(app)

def setup_function():
    db.reset()
    db.seed(Order(id="ord_legacy", customer_id="c1", total_cents=1000, status="open", hold_reason=None))
    db.seed(Order(id="ord_new", customer_id="c2", total_cents=2500, status="open", hold_reason=None))

def test_get_legacy_order_shape():
    res = client.get("/orders/ord_legacy")
    assert res.status_code == 200
    assert res.json()["id"] == "ord_legacy"

def test_hold_sets_status():
    res = client.post("/orders/ord_new/hold", json={"hold_reason": "fraud_review"})
    assert res.status_code == 200
    assert res.json()["status"] == "on_hold"

def test_release_clears_hold():
    client.post("/orders/ord_new/hold", json={"hold_reason": "stock"})
    res = client.post("/orders/ord_new/release")
    assert res.status_code == 200
    assert res.json()["status"] == "open"

def test_hold_reason_round_trip_and_legacy_null():
    assert client.get("/orders/ord_legacy").json().get("hold_reason") is None
    client.post("/orders/ord_new/hold", json={"hold_reason": "fraud_review"})
    assert client.get("/orders/ord_new").json()["hold_reason"] == "fraud_review"

def test_replacing_reason_preserves_money_and_other_orders():
    client.post('/orders/ord_new/hold', json={'hold_reason': 'first'})
    response = client.post('/orders/ord_new/hold', json={'hold_reason': 'Révision 仓库'})
    assert response.status_code == 200
    saved = client.get('/orders/ord_new').json()
    assert saved['hold_reason'] == 'Révision 仓库'
    assert saved['total_cents'] == 2500
    assert saved['customer_id'] == 'c2'
    legacy = client.get('/orders/ord_legacy').json()
    assert legacy['status'] == 'open'
    assert legacy['hold_reason'] is None

def test_optional_reason_and_repeat_release():
    held = client.post('/orders/ord_new/hold', json={})
    assert held.status_code == 200
    assert held.json()['hold_reason'] is None
    for _ in range(2):
        released = client.post('/orders/ord_new/release')
        assert released.status_code == 200
        assert released.json()['status'] == 'open'
        assert released.json()['hold_reason'] is None
```

### Exact trusted behavioral probes

#### reason-persists — weight 4

Probe (observation adapter body, not a standalone program):

```python
from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.models import Order
db.reset()
db.seed(Order('probe','buyer',197))
c=TestClient(app)
r=c.post('/orders/probe/hold',json={'hold_reason':'warehouse review 73'});g=c.get('/orders/probe'); result=[r.status_code,r.json().get('hold_reason'),g.json().get('hold_reason'),g.json().get('status'),g.json().get('total_cents')]
```

Expected JSON:

```json
[
  200,
  "warehouse review 73",
  "warehouse review 73",
  "on_hold",
  197
]
```

#### legacy-null — weight 2

Probe (observation adapter body, not a standalone program):

```python
from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.models import Order
db.reset()
db.seed(Order('probe','buyer',197))
c=TestClient(app)
result=c.get('/orders/probe').json().get('hold_reason','MISSING')
```

Expected JSON:

```json
null
```

#### release-clears — weight 2

Probe (observation adapter body, not a standalone program):

```python
from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.models import Order
db.reset()
db.seed(Order('probe','buyer',197))
c=TestClient(app)
c.post('/orders/probe/hold',json={'hold_reason':'review'});r=c.post('/orders/probe/release');result=[r.json().get('status'),c.get('/orders/probe').json().get('hold_reason','MISSING')]
```

Expected JSON:

```json
[
  "open",
  null
]
```

#### missing-order — weight 1

Probe (observation adapter body, not a standalone program):

```python
from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.models import Order
db.reset()
db.seed(Order('probe','buyer',197))
c=TestClient(app)
result=c.post('/orders/absent/hold',json={'hold_reason':'x'}).status_code
```

Expected JSON:

```json
404
```

#### reason-overwrite-and-isolation — weight 3

Probe (observation adapter body, not a standalone program):

```python
from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.models import Order
db.reset()
db.seed(Order('probe','buyer',197))
c=TestClient(app)
db.seed(Order('other','second',503))
c.post('/orders/probe/hold',json={'hold_reason':'first'})
c.post('/orders/probe/hold',json={'hold_reason':'Révision 仓库'})
a=c.get('/orders/probe').json(); b=c.get('/orders/other').json()
result=[a.get('hold_reason'),a.get('customer_id'),a.get('total_cents'),b.get('status'),b.get('hold_reason','MISSING'),b.get('total_cents')]
```

Expected JSON:

```json
[
  "Révision 仓库",
  "buyer",
  197,
  "open",
  null,
  503
]
```

#### optional-reason-and-repeat-release — weight 2

Probe (observation adapter body, not a standalone program):

```python
from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.models import Order
db.reset()
db.seed(Order('probe','buyer',197))
c=TestClient(app)
r=c.post('/orders/probe/hold',json={})
c.post('/orders/probe/release'); r2=c.post('/orders/probe/release')
result=[r.status_code,r.json().get('status'),r.json().get('hold_reason','MISSING'),r2.status_code,r2.json().get('status'),r2.json().get('hold_reason','MISSING')]
```

Expected JSON:

```json
[
  200,
  "on_hold",
  null,
  200,
  "open",
  null
]
```

### Remaining review requirement

No additional manual gap is registered in this snapshot. That does not prove exhaustive correctness beyond the supplied contracts and fixtures.

## 28. workspace-label-propagation

[Candidate README](/Users/shrutwik/Desktop/PromptCode/challenges/workspace-label-propagation/README.md) · Trusted inventory digest: `ca96550c6762e0112f21593a87ec45930ce2abdd1a9f7d5416e75c974dd56a75`

### Exact candidate instructions

````text
# Ticket labels

You are on tickets. The workspace already has a fixed set of labels. Agents are pasting tags into the title because the labels they check are gone after save, so the queue filters lie.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

A label is an id and a name, scoped to one workspace. A ticket stores label ids.

`PUT /tickets/:id/labels` with ids from that workspace returns those ids, and the next GET returns the same ids. An id that is not in the workspace is rejected with 400.

The ticket screen shows the label ids the server stored.

The export spreadsheet is a hypothesis for where labels went.

## Getting started

```bash
npm install
npm test
```
````

### Exact visible test source and fixtures

#### client.test.tsx

[Source](/Users/shrutwik/Desktop/PromptCode/challenges/workspace-label-propagation/tests/client.test.tsx) · SHA-256 `dccd11d669bee105cd90829cba4d437f093cc5cf00a9396550dc86eb65b94ce9`

Named tests: `loads selected from ticket.labelIds`

```typescript
// @vitest-environment jsdom
import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { TicketLabels } from '../client/TicketLabels';
import { setBaseUrl } from '../client/api';
beforeEach(() => {
  setBaseUrl('http://example.test');
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/tickets/t1') && !u.includes('/labels')) {
      return { ok: true, json: async () => ({ id: 't1', workspaceId: 'ws1', title: 'Login broken', labelIds: ['lbl_bug'] }) };
    }
    if (u.includes('/workspaces/')) {
      return { ok: true, json: async () => [{ id: 'lbl_bug', name: 'Bug' }, { id: 'lbl_urgent', name: 'Urgent' }] };
    }
    return { ok: true, json: async () => ({}) };
  }));
});
it('loads selected from ticket.labelIds', async () => {
  render(<TicketLabels ticketId="t1" />);
  await waitFor(() => expect(screen.getByTestId('title').textContent).toBe('Login broken'));
  await waitFor(() => expect(screen.getByTestId('selected').textContent).toBe('lbl_bug'));
});
```

#### labels.roundtrip.test.ts

[Source](/Users/shrutwik/Desktop/PromptCode/challenges/workspace-label-propagation/tests/labels.roundtrip.test.ts) · SHA-256 `418fe63aa5b002e5184976b1f8810ce63d1302b4f4784c2514f4792767c21d74`

Named tests: `round trips labelIds`

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import request from 'supertest';
import { createApp } from '../server/app.js';
import * as db from '../server/db.js';
const app = createApp();
beforeEach(() => {
  db.resetDb();
  db.seedWorkspace('ws1', [{ id: 'lbl_bug', name: 'Bug' }, { id: 'lbl_urgent', name: 'Urgent' }]);
  db.seedTicket({ id: 't1', workspaceId: 'ws1', title: 'Login broken', labelIds: [] });
});
it('round trips labelIds', async () => {
  const put = await request(app).put('/tickets/t1/labels').send({ labelIds: ['lbl_bug', 'lbl_urgent'] });
  expect(put.status).toBe(200);
  expect(put.body.labelIds).toEqual(['lbl_bug', 'lbl_urgent']);
  expect((await request(app).get('/tickets/t1')).body.labelIds).toEqual(['lbl_bug', 'lbl_urgent']);
});
```

#### server.test.ts

[Source](/Users/shrutwik/Desktop/PromptCode/challenges/workspace-label-propagation/tests/server.test.ts) · SHA-256 `e017325fce8621a5b3d3a1fc0928789858967718585f304ae1b3b4f54f899bb3`

Named tests: `rejects mixed foreign labels without erasing saved labels`, `clears persisted labels with an empty list`, `gets core fields`, `rejects unknown labels`, `lists labels`

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import request from 'supertest';
import { createApp } from '../server/app.js';
import * as db from '../server/db.js';
const app = createApp();
beforeEach(() => {
  db.resetDb();
  db.seedWorkspace('ws1', [{ id: 'lbl_bug', name: 'Bug' }, { id: 'lbl_urgent', name: 'Urgent' }]);
  db.seedTicket({ id: 't1', workspaceId: 'ws1', title: 'Login broken', labelIds: ['lbl_bug'] });
});
describe('API', () => {
  it('rejects mixed foreign labels without erasing saved labels', async () => {
    db.seedWorkspace('other', [{ id: 'private', name: 'Private' }]);
    const before = db.getTicket('t1');
    const response = await request(app).put('/tickets/t1/labels').send({ labelIds: ['lbl_urgent', 'private'] });
    expect(response.status).toBe(400);
    expect(db.getTicket('t1')).toEqual(before);
    expect((await request(app).get('/tickets/t1')).body.labelIds).toEqual(['lbl_bug']);
  });
  it('clears persisted labels with an empty list', async () => {
    expect((await request(app).put('/tickets/t1/labels').send({ labelIds: [] })).status).toBe(200);
    expect((await request(app).get('/tickets/t1')).body.labelIds).toEqual([]);
  });
  it('gets core fields', async () => {
    const res = await request(app).get('/tickets/t1');
    expect(res.status).toBe(200);
    expect(res.body.title).toBe('Login broken');
  });
  it('rejects unknown labels', async () => {
    expect((await request(app).put('/tickets/t1/labels').send({ labelIds: ['nope'] })).status).toBe(400);
  });
  it('lists labels', async () => {
    expect((await request(app).get('/workspaces/ws1/labels')).body).toHaveLength(2);
  });
});
```

### Exact trusted behavioral probes

#### persist-roundtrip — weight 4

Probe (observation adapter body, not a standalone program):

```typescript
import request from 'supertest';import {createApp} from './server/app';import * as db from './server/db';db.resetDb();db.seedWorkspace('ours',[{id:'a',name:'Urgent'},{id:'b',name:'Review'}]);db.seedWorkspace('other',[{id:'foreign',name:'Private'}]);db.seedTicket({id:'ticket',workspaceId:'ours',title:'T'});const api=request(createApp());const put=await api.put('/tickets/ticket/labels').send({labelIds:['b','a']});const get=await api.get('/tickets/ticket');return [put.status,put.body.labelIds,get.body.labelIds];
```

Expected JSON:

```json
[
  200,
  [
    "b",
    "a"
  ],
  [
    "b",
    "a"
  ]
]
```

#### cross-workspace-rejected — weight 3

Probe (observation adapter body, not a standalone program):

```typescript
import request from 'supertest';import {createApp} from './server/app';import * as db from './server/db';db.resetDb();db.seedWorkspace('ours',[{id:'a',name:'Urgent'},{id:'b',name:'Review'}]);db.seedWorkspace('other',[{id:'foreign',name:'Private'}]);db.seedTicket({id:'ticket',workspaceId:'ours',title:'T'});const api=request(createApp());const put=await api.put('/tickets/ticket/labels').send({labelIds:['foreign']});return [put.status,db.getTicket('ticket').labelIds];
```

Expected JSON:

```json
[
  400,
  []
]
```

#### clear-labels — weight 2

Probe (observation adapter body, not a standalone program):

```typescript
import request from 'supertest';import {createApp} from './server/app';import * as db from './server/db';db.resetDb();db.seedWorkspace('ours',[{id:'a',name:'Urgent'},{id:'b',name:'Review'}]);db.seedWorkspace('other',[{id:'foreign',name:'Private'}]);db.seedTicket({id:'ticket',workspaceId:'ours',title:'T'});const api=request(createApp());await api.put('/tickets/ticket/labels').send({labelIds:['a']});await api.put('/tickets/ticket/labels').send({labelIds:[]});return (await api.get('/tickets/ticket')).body.labelIds;
```

Expected JSON:

```json
[]
```

#### invalid-update-preserves-labels — weight 3

Probe (observation adapter body, not a standalone program):

```typescript
import request from 'supertest';import {createApp} from './server/app';import * as db from './server/db';db.resetDb();db.seedWorkspace('ours',[{id:'a',name:'Urgent'},{id:'b',name:'Review'}]);db.seedWorkspace('other',[{id:'foreign',name:'Private'}]);db.seedTicket({id:'ticket',workspaceId:'ours',title:'T'});const api=request(createApp());await api.put('/tickets/ticket/labels').send({labelIds:['a']});const r=await api.put('/tickets/ticket/labels').send({labelIds:['b','foreign']});return [r.status,(await api.get('/tickets/ticket')).body.labelIds];
```

Expected JSON:

```json
[
  400,
  [
    "a"
  ]
]
```

#### workspace-list-isolation — weight 2

Probe (observation adapter body, not a standalone program):

```typescript
import request from 'supertest';import {createApp} from './server/app';import * as db from './server/db';db.resetDb();db.seedWorkspace('ours',[{id:'a',name:'Urgent'},{id:'b',name:'Review'}]);db.seedWorkspace('other',[{id:'foreign',name:'Private'}]);db.seedTicket({id:'ticket',workspaceId:'ours',title:'T'});const api=request(createApp());return [(await api.get('/workspaces/ours/labels')).body,(await api.put('/tickets/missing/labels').send({labelIds:['a']})).status];
```

Expected JSON:

```json
[
  [
    {
      "id": "a",
      "name": "Urgent"
    },
    {
      "id": "b",
      "name": "Review"
    }
  ],
  404
]
```

### Remaining review requirement

React screen displays persisted labels

## 29. catalog-suggest-latency

[Candidate README](/Users/shrutwik/Desktop/PromptCode/challenges/catalog-suggest-latency/README.md) · Trusted inventory digest: `92acac499d2ee80190b887d020dbfcd2081e28c6aa0092da9f8499f3f5728b69`

### Exact candidate instructions

````text
# Search suggest

You are on catalog search. Shoppers typing in electronics wait long enough that suggest feels hung.

Product will ship a faster list only if it ranks the same products in the same order as today. The catalog in this repo is in memory, about 10,000 products, with id, title, category, popularity, and tokens.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

`suggest` stays in the current rank order: higher score, then higher popularity, then id ascending.

On the 10,000-product catalog the tests build, a query finishes in under 200ms and the scan counter stays under 20,000.

A cache in front of suggest is a hypothesis. Measure the work a query does before you add one.

## Getting started

```bash
npm install
npm test
```
````

### Exact visible test source and fixtures

#### suggest.test.ts

[Source](/Users/shrutwik/Desktop/PromptCode/challenges/catalog-suggest-latency/tests/suggest.test.ts) · SHA-256 `9785270e8e6221765c1a3464258648bbcd6cbaff04334e423e70d61e4136c1fd`

Named tests: `handles empty input, whitespace queries, and an explicit zero limit`, `ranks multiple normalized tokens without mutating the catalog`, `deterministic ids`, `compareRank ordering`, `warmed median suggest latency stays under 200ms on 10k`, `scan work grows linearly across catalog sizes`, `fewer than 20k scans on 10k catalog`

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { buildCatalog } from '../src/catalog.js';
import { suggest } from '../src/suggest.js';
import { scoreProduct, compareRank } from '../src/rank.js';
import { globalCounter } from '../src/queryCounter.js';
import { resetCatalog, suggestProducts, scanCount } from '../src/service.js';
beforeEach(() => { globalCounter.reset(); resetCatalog(10_000); });
describe('ranking', () => {
  it('handles empty input, whitespace queries, and an explicit zero limit', () => {
    const rows = [{ id: 'a', title: 'A', category: 'phone', popularity: 1, tokens: ['phone'] }];
    expect(suggest([], 'phone')).toEqual([]);
    expect(suggest(rows, '   ')).toEqual([]);
    expect(suggest(rows, 'phone', { limit: 0 })).toEqual([]);
  });
  it('ranks multiple normalized tokens without mutating the catalog', () => {
    const rows = [{ id: 'b', title: 'B', category: 'x', popularity: 100, tokens: ['phone'] },
      { id: 'a', title: 'A', category: 'case', popularity: 1, tokens: ['phone', 'case'] }];
    const before = JSON.stringify(rows);
    expect(suggest(rows, ' PHONE   case ').map(row => row.id)).toEqual(['a', 'b']);
    expect(JSON.stringify(rows)).toBe(before);
  });
  it('deterministic ids', () => {
    const catalog = buildCatalog(500);
    globalCounter.reset();
    const a = suggest(catalog, 'kitchen item', { limit: 5 }).map((p) => p.id);
    globalCounter.reset();
    const b = suggest(catalog, 'kitchen item', { limit: 5 }).map((p) => p.id);
    expect(a).toEqual(b);
  });
  it('compareRank ordering', () => {
    const catalog = buildCatalog(20);
    const rows = catalog.map((product) => ({ score: scoreProduct(['tools'], product), product }));
    rows.sort(compareRank);
    for (let i = 1; i < rows.length; i++) expect(compareRank(rows[i - 1], rows[i])).toBeLessThanOrEqual(0);
  });
});
describe('latency and scans', () => {
  it('warmed median suggest latency stays under 200ms on 10k', () => {
    for (let i = 0; i < 3; i++) suggestProducts('electronics item', 10);
    const samples = Array.from({ length: 7 }, () => {
      const start = performance.now();
      const results = suggestProducts('electronics item', 10);
      const elapsed = performance.now() - start;
      expect(results.length).toBe(10);
      return elapsed;
    }).sort((a, b) => a - b);
    expect(samples[3]).toBeLessThan(200);
  });
  it('scan work grows linearly across catalog sizes', () => {
    for (const size of [100, 1000, 10000]) {
      resetCatalog(size);
      suggestProducts('garden item', 10);
      expect(scanCount()).toBeGreaterThanOrEqual(size);
      expect(scanCount()).toBeLessThanOrEqual(size * 2);
    }
  });
  it('fewer than 20k scans on 10k catalog', () => {
    suggestProducts('garden item', 10);
    expect(scanCount()).toBeLessThan(20_000);
  });
});
```

### Exact trusted behavioral probes

#### ranking-ties — weight 4

Probe (observation adapter body, not a standalone program):

```typescript
import {suggest} from './src/suggest';const rows=[{id:'b',title:'B',category:'x',popularity:7,tokens:['phone']},{id:'a',title:'A',category:'x',popularity:7,tokens:['phone']},{id:'z',title:'Z',category:'phone',popularity:99,tokens:[]},{id:'c',title:'C',category:'phone',popularity:1,tokens:['phone']}];return suggest(rows,' PHONE ').map(r=>r.id);
```

Expected JSON:

```json
[
  "c",
  "a",
  "b",
  "z"
]
```

#### no-match-and-limit — weight 2

Probe (observation adapter body, not a standalone program):

```typescript
import {suggest} from './src/suggest';const rows=Array.from({length:31},(_,i)=>({id:String(i).padStart(3,'0'),title:'a',category:'x',popularity:i,tokens:['word']}));return [suggest(rows,'absent'),suggest(rows,'word',{limit:3}).map(r=>r.id)];
```

Expected JSON:

```json
[
  [],
  [
    "030",
    "029",
    "028"
  ]
]
```

#### large-catalog-ranking — weight 3

Probe (observation adapter body, not a standalone program):

```typescript
import {suggest} from './src/suggest';const rows=Array.from({length:10000},(_,i)=>({id:String(i).padStart(5,'0'),title:'item',category:'x',popularity:i,tokens:['word']}));return suggest(rows,'word',{limit:3}).map(r=>r.id);
```

Expected JSON:

```json
[
  "09999",
  "09998",
  "09997"
]
```

#### empty-query-and-zero-limit — weight 2

Probe (observation adapter body, not a standalone program):

```typescript
import {suggest} from './src/suggest';const rows=[{id:'a',title:'A',category:'phone',popularity:1,tokens:['phone']}];return [suggest([],'phone'),suggest(rows,'   '),suggest(rows,'phone',{limit:0})];
```

Expected JSON:

```json
[
  [],
  [],
  []
]
```

#### multi-token-no-input-mutation — weight 3

Probe (observation adapter body, not a standalone program):

```typescript
import {suggest} from './src/suggest';const rows=[{id:'b',title:'B',category:'x',popularity:100,tokens:['phone']},{id:'a',title:'A',category:'case',popularity:1,tokens:['phone','case']}];const before=JSON.stringify(rows);const ids=suggest(rows,' PHONE   case ').map(r=>r.id);return [ids,JSON.stringify(rows)===before];
```

Expected JSON:

```json
[
  [
    "a",
    "b"
  ],
  true
]
```

### Remaining review requirement

200ms latency under calibrated load; scan instrumentation cannot be self-attested

## 30. pricing-rule-extract

[Candidate README](/Users/shrutwik/Desktop/PromptCode/challenges/pricing-rule-extract/README.md) · Trusted inventory digest: `dba4f84db380149d2f0b6e28342393d288349d82a054f4a4d2a610e7612db5ea`

### Exact candidate instructions

````text
# Pricing rules

You are in pricing. Quotes are correct, and finance trusts the golden cents. The rule loop is buried inside `quote()`, and the next pricing change is unsafe until that loop can be read on its own.

Percent-off and amount-off do not commute once you round.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

Add `applyRules(baseCents, rules)`. It applies `percent_off`, then `amount_off`, then `surcharge_percent`, with the same half-up rounding, and returns the same `finalCents` and applied codes as `quote()`.

`quote()` calls `applyRules` and keeps its current signature. A negative result floors at 0. An empty rule list returns the base.

If a golden cent moves, the extract is wrong. Leave the expectations alone.

## Getting started

```bash
npm install
npm test
```
````

### Exact visible test source and fixtures

#### pricing.test.ts

[Source](/Users/shrutwik/Desktop/PromptCode/challenges/pricing-rule-extract/tests/pricing.test.ts) · SHA-256 `593b6584f397d8d33da4ea71dc99e12e14af1422012c9bdbf75316720143b9c3`

Named tests: `rounds half cents up for both discounts and surcharges`, `does not mutate rules across repeated quotes`, `applies percent then amount then surcharge`, `half-up rounding`, `empty rules`, `zero base non-negative`, `applyRules matches quote`

```typescript
import { describe, it, expect } from 'vitest';
import { quote, applyRules } from '../src/pricingEngine.js';
import { roundHalfUp } from '../src/money.js';
describe('golden quotes', () => {
  it('rounds half cents up for both discounts and surcharges', () => {
    expect(applyRules(5, [{ type: 'percent_off', pct: 10, code: 'p' }])).toEqual({ finalCents: 4, applied: ['p'] });
    expect(quote({ baseCents: 5, rules: [{ type: 'surcharge_percent', pct: 10, code: 's' }] })).toEqual({ finalCents: 6, applied: ['s'] });
  });
  it('does not mutate rules across repeated quotes', () => {
    const input = { baseCents: 100, rules: [{ type: 'surcharge_percent' as const, pct: 10, code: 's' },
      { type: 'amount_off' as const, cents: 7, code: 'a' }] };
    const before = JSON.stringify(input);
    const expected = { finalCents: 102, applied: ['a', 's'] };
    expect(quote(input)).toEqual(expected);
    expect(applyRules(input.baseCents, input.rules)).toEqual(expected);
    expect(JSON.stringify(input)).toBe(before);
  });
  it('applies percent then amount then surcharge', () => {
    const result = quote({
      baseCents: 10000,
      rules: [
        { type: 'surcharge_percent', pct: 10, code: 'surch' },
        { type: 'amount_off', cents: 500, code: 'flat' },
        { type: 'percent_off', pct: 15, code: 'vip' },
      ],
    });
    expect(result.finalCents).toBe(8800);
    expect(result.applied).toEqual(['vip', 'flat', 'surch']);
  });
  it('half-up rounding', () => {
    expect(roundHalfUp(2.5)).toBe(3);
    const result = quote({ baseCents: 1001, rules: [{ type: 'percent_off', pct: 10, code: 'p' }] });
    expect(result.finalCents).toBe(1001 - roundHalfUp((1001 * 10) / 100));
  });
  it('empty rules', () => { expect(quote({ baseCents: 42, rules: [] }).finalCents).toBe(42); });
  it('zero base non-negative', () => {
    expect(quote({ baseCents: 0, rules: [{ type: 'amount_off', cents: 50, code: 'x' }] }).finalCents).toBe(0);
  });
  it('applyRules matches quote', () => {
    const rules = [{ type: 'percent_off' as const, pct: 5, code: 'a' }, { type: 'amount_off' as const, cents: 10, code: 'b' }];
    expect(applyRules(2000, rules)).toEqual(quote({ baseCents: 2000, rules }));
  });
});
```

### Exact trusted behavioral probes

#### order-and-rounding — weight 4

Probe (observation adapter body, not a standalone program):

```typescript
import {quote,applyRules} from './src/pricingEngine';const rules=[{type:'surcharge_percent',pct:5,code:'s'},{type:'amount_off',cents:17,code:'a'},{type:'percent_off',pct:10,code:'p'}];return [applyRules(105,rules),quote({baseCents:105,rules})];
```

Expected JSON:

```json
[
  {
    "finalCents": 81,
    "applied": [
      "p",
      "a",
      "s"
    ]
  },
  {
    "finalCents": 81,
    "applied": [
      "p",
      "a",
      "s"
    ]
  }
]
```

#### floor-zero — weight 2

Probe (observation adapter body, not a standalone program):

```typescript
import {quote,applyRules} from './src/pricingEngine';return applyRules(5,[{type:'amount_off',cents:9,code:'discount'}]);
```

Expected JSON:

```json
{
  "finalCents": 0,
  "applied": [
    "discount"
  ]
}
```

#### empty-preserves — weight 2

Probe (observation adapter body, not a standalone program):

```typescript
import {quote,applyRules} from './src/pricingEngine';return applyRules(137,[]);
```

Expected JSON:

```json
{
  "finalCents": 137,
  "applied": []
}
```

#### same-type-order — weight 2

Probe (observation adapter body, not a standalone program):

```typescript
import {quote,applyRules} from './src/pricingEngine';return applyRules(100,[{type:'amount_off',cents:2,code:'z'},{type:'amount_off',cents:3,code:'a'}]);
```

Expected JSON:

```json
{
  "finalCents": 95,
  "applied": [
    "a",
    "z"
  ]
}
```

#### half-cent-rounding — weight 3

Probe (observation adapter body, not a standalone program):

```typescript
import {quote,applyRules} from './src/pricingEngine';return [applyRules(5,[{type:'percent_off',pct:10,code:'p'}]),quote({baseCents:5,rules:[{type:'surcharge_percent',pct:10,code:'s'}]})];
```

Expected JSON:

```json
[
  {
    "finalCents": 4,
    "applied": [
      "p"
    ]
  },
  {
    "finalCents": 6,
    "applied": [
      "s"
    ]
  }
]
```

#### repeated-call-no-input-mutation — weight 2

Probe (observation adapter body, not a standalone program):

```typescript
import {quote,applyRules} from './src/pricingEngine';const rules=[{type:'surcharge_percent',pct:10,code:'s'},{type:'amount_off',cents:7,code:'a'}];const before=JSON.stringify(rules);return [applyRules(100,rules),quote({baseCents:100,rules}),JSON.stringify(rules)===before];
```

Expected JSON:

```json
[
  {
    "finalCents": 102,
    "applied": [
      "a",
      "s"
    ]
  },
  {
    "finalCents": 102,
    "applied": [
      "a",
      "s"
    ]
  },
  true
]
```

### Remaining review requirement

quote delegates to extracted applyRules; source review
