# Medium Challenge Audit — Batch B

Audited: 2026-09-18. All five challenges left in **STARTER (buggy/incomplete) state** after reference verification.

---

### shipment-csv-merge

- **Starter tests:** `cd challenges/shipment-csv-merge && .venv/bin/pytest -q` → **2 passed, 2 failed**. Intentional failures: `test_duplicate_event_id_across_batches_not_double_counted`, `test_same_status_different_event_ids_kept_in_ts_order`. Baseline passes: `test_basic_timeline_order_happy_path`, `test_quantity_single_batch`.
- **Reference tests:** After applying SOLUTION fix (dedupe by `event_id`, qty once) → **4/4 pass**. Restored starter afterward.
- **Difficulty:** Medium 25–35 min — appropriate. Dedupe-key bug with qty side-effect is realistic ops work, not LeetCode.
- **AI trap:** Dedupe by `(shipment_id, status)` instead of `event_id`, dropping legitimate same-status events or still double-counting qty on skipped rows.
- **Irrelevant file:** `shipment_merge/email_template.py` (late-shipment email helper; unreferenced, not in README).
- **SOLUTION sections:** Complete (16/16). All required sections present: root cause, investigation path, reference impl, wrong alternatives, AI failure modes, edge cases, verification, complexity, Expected Event Timeline, positive/negative/recovery signals, Rubric A–G /100, Interviewer Observations, Defend-Your-Code (4). Nothing added.
- **Changes made:**
  - None (starter verified runnable; reference fix tested transiently then reverted).
- **Risks/remaining:** Global `pytest` outside `.venv` hits pydantic plugin conflict — README correctly documents venv path. `summarize.py` is used by tests (not noise).

---

### tenant-document-acl

- **Starter tests:** `cd challenges/tenant-document-acl && .venv/bin/pytest -q` → **3 passed, 2 failed**. Intentional failures: `test_cross_tenant_get_is_404`, `test_cross_tenant_patch_is_404`. Baseline: list scoping, owner read, missing-doc 404.
- **Reference tests:** After tenant ownership check in `app/service.py` → **5/5 pass**. Restored starter.
- **Difficulty:** Medium 25–30 min — appropriate IDOR fix with 404-oracle nuance.
- **AI trap:** Return 403 after existence check (leaks cross-tenant doc IDs) or patch GET only and miss PATCH path.
- **Irrelevant file:** `app/billing_hooks.py` (seat-change stub; unreferenced, not in README).
- **SOLUTION sections:** Complete (16/16). Nothing added.
- **Changes made:** None.
- **Risks/remaining:** Starlette deprecation warnings only; no functional impact.

---

### webhook-delivery-retry

- **Starter tests:** `cd challenges/webhook-delivery-retry && npm test` → **1 passed, 2 failed**. Intentional failures: `does not charge more than once per successful delivery id` (chargeCount=3), `bounds concurrent outbound posts when delivering a batch` (maxInFlight=20). Baseline: `eventually succeeds after transient failures`.
- **Reference tests:** After moving `recordCharge` to success path + worker pool (limit 5) → **3/3 pass**. Restored starter.
- **Difficulty:** Medium 30–35 min — appropriate two-part fix (idempotency then concurrency).
- **AI trap:** Add `X-Delivery-Id` header or retry tuning without moving charge; rewrite with unbounded `Promise.all`.
- **Irrelevant file:** `src/analytics.ts` (delivery analytics stub; unreferenced, not in README).
- **SOLUTION sections:** Complete (16/16). Nothing added.
- **Changes made:** None.
- **Risks/remaining:** None significant.

---

### pricing-rule-extract

- **Starter tests:** `cd challenges/pricing-rule-extract && npm test` → **5 passed, 0 failed**. All green by design — behavior-preserving refactor; `applyRules` circularly delegates to `quote` (incomplete extract).
- **Reference tests:** After extracting loop into `applyRules` with `quote` delegating → **5/5 pass**. Restored starter (circular delegation).
- **Difficulty:** Medium 25–30 min — appropriate refactor under green tests; not trivial (ordering + half-up rounding invariants).
- **AI trap:** Reorder rule application or change rounding to “simplify,” breaking golden quotes without touching test expectations.
- **Irrelevant file:** `src/catalogCopy.ts` (marketing copy constants; unreferenced, not in README).
- **SOLUTION sections:** Complete (16/16). Nothing added.
- **Changes made:** None.
- **Risks/remaining:** Candidate must resist editing golden expectations; rubric E covers this.

---

### subscription-proration-boundary

- **Starter tests:** `cd challenges/subscription-proration-boundary && .venv/bin/pytest -q` → **4 passed, 0 failed**. All green by design — inclusive-end bug hidden from public suite.
- **Reference tests:** After half-open fix (`start <= instant < end`) → public **4/4 pass** + hidden evaluator case from SOLUTION passes (`contains(period.end) is False`, credit=0 at period rollover). Restored starter (inclusive end).
- **Difficulty:** Medium 25–35 min — appropriate “looks-correct” challenge; display red herring in README/ticket.
- **AI trap:** Patch `format_display` timezone formatting (README red herring) instead of fixing `contains` boundary semantics.
- **Irrelevant file:** `proration/ledger_export.py` (CSV export stub; unreferenced, not in README).
- **SOLUTION sections:** Complete (17/17, includes Hidden evaluator cases). Nothing added.
- **Changes made:** None.
- **Risks/remaining:** Interviewer must run hidden boundary case at eval time; public suite alone cannot distinguish strong vs weak candidates.

---

## Batch Summary

| Challenge | Starter | Reference | Starter state restored |
|-----------|---------|-----------|------------------------|
| shipment-csv-merge | 2✓ 2✗ | 4✓ | Yes |
| tenant-document-acl | 3✓ 2✗ | 5✓ | Yes |
| webhook-delivery-retry | 1✓ 2✗ | 3✓ | Yes |
| pricing-rule-extract | 5✓ 0✗ | 5✓ | Yes |
| subscription-proration-boundary | 4✓ 0✗ | 4✓ + hidden | Yes |

**No challenge.json eval files touched.** No source/SOLUTION edits persisted — batch is interview-ready as-is.
