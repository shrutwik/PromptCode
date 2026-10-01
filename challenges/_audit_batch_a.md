# Medium Challenge Audit — Batch A

Audited: 2026-09-18. All five challenges left in **STARTER (buggy)** state after solution verification.

---

### invoice-status-transition

- **Starter tests:** `npm test` — **5 passed / 1 failed (6 total)**. Intentional fail: `allowed transitions > rejects paid -> draft` (`canTransition('paid','draft')` returns true due to buggy special-case in `statusMachine.ts`).
- **Reference tests:** After removing paid special-case in `canTransition`, **all 6 pass**. Solution matches SOLUTION.md.
- **Difficulty:** Medium 25–30 min. Appropriate — ticket misdirects to timezone; candidate must reproduce, ignore red herring, fix state machine. Not LeetCode.
- **AI trap:** Ticket blames timezone formatting; `timezoneFormat.ts` is unused on mutation path — AI patches dates first.
- **Irrelevant file:** `src/timezoneFormat.ts` (also `src/auditLog.ts` — debug stub, unmentioned in README).
- **SOLUTION sections:** Complete — all required sections present (root cause through Defend-Your-Code). No additions needed.
- **Changes made:**
  - Added failing regression test `rejects paid -> draft` to `tests/statusMachine.test.ts` (starter had zero failing tests despite documented bug).
  - Updated README acceptance: "Regression test for paid → draft must pass" (was "Add").
- **Risks/remaining:** None. Starter now correctly demonstrates the finance bug via test failure.

---

### order-hold-reason

- **Starter tests:** `pytest -q` (via `.venv/bin/python -m pytest -q`) — **3 passed / 1 failed (4 total)**. Intentional fail: `test_hold_reason_round_trip_and_legacy_null` (KeyError — `hold_reason` omitted from `to_public_dict`).
- **Reference tests:** After adding `"hold_reason": order.hold_reason` to `to_public_dict`, **all 4 pass**.
- **Difficulty:** Medium 25–30 min. Progressive Part A/B structure fits window. Baseline hold/release tests pass; one integration test fails.
- **AI trap:** AI over-validates hold_reason as required string, breaking legacy null orders.
- **Irrelevant file:** `app/metrics_stub.py` (unused hold counter stub).
- **SOLUTION sections:** Complete. No additions needed.
- **Changes made:** None (starter already correct).
- **Risks/remaining:** README documents `python3 -m venv` setup; use `python3`/` .venv/bin/python` on systems without `python` shim.

---

### catalog-suggest-latency

- **Starter tests:** `npm test` — **2 passed / 2 failed (4 total)**. Intentional fails: `suggest under 200ms on 10k` (~242ms), `fewer than 20k scans on 10k catalog` (100M scans — n² inner loop records `catalog.length` per product).
- **Reference tests:** After single-pass fix (one `recordScan(catalog.length)`, remove inner loop), **all 4 pass**. Ranking tests unchanged.
- **Difficulty:** Medium 25–35 min. Perf + algorithm, not LeetCode. Scan counter contract prevents cheating ranking.
- **AI trap:** AI adds memoization/cache via `indexCache.ts` without fixing O(n²) loop.
- **Irrelevant file:** `src/indexCache.ts` (feature-flag stub, unused by suggest path).
- **SOLUTION sections:** Complete. No additions needed.
- **Changes made:** None (starter already correct).
- **Risks/remaining:** Latency threshold (200ms) may be tight on slow CI; passes locally on M-series Mac.

---

### notification-feed-stale

- **Starter tests:** `npm test` — **2 passed / 1 failed (3 total)**. Intentional fail: `concurrency > marks two without clobber` (stale snapshot in `markAsRead` clobbers concurrent updates).
- **Reference tests:** After removing pre-await snapshot pattern, **all 3 pass**.
- **Difficulty:** Medium 25–30 min. Classic async closure bug; ticket misdirects to React keys.
- **AI trap:** AI fixes `NotificationList` keys/remount only, leaves stale snapshot in store.
- **Irrelevant file:** `src/theme.ts` (color constants, unused).
- **SOLUTION sections:** Complete. No additions needed.
- **Changes made:**
  - Added `afterEach(cleanup)` to `tests/feed.test.tsx` — UI tests were leaking DOM between cases (false failure when solution applied).
- **Risks/remaining:** None after cleanup fix.

---

### workspace-label-propagation

- **Starter tests:** `npm test` — **3 passed / 2 failed (5 total)**. Intentional fails: `round trips labelIds` (API omits field on GET/PUT), `loads selected from ticket.labelIds` (UI hardcodes `setSelected([])`).
- **Reference tests:** After adding `labelIds` to API responses and `setSelected(ticket.labelIds ?? [])`, **all 5 pass**.
- **Difficulty:** Medium 30–35 min. Three-part progressive (persist/API/UI). Upper bound of Medium window but scoped.
- **AI trap:** AI rewrites to free-text tags or fixes API without wiring UI initial load.
- **Irrelevant file:** `server/legacyExport.ts` (CSV export helper, unused).
- **SOLUTION sections:** Complete. No additions needed.
- **Changes made:** None (starter already correct).
- **Risks/remaining:** Duplicate component paths (`src/` vs `client/`) may confuse; tests target `client/TicketLabels.tsx` and `server/app.ts`.

---

## Summary

| Challenge | Starter | Solution | Status |
|-----------|---------|----------|--------|
| invoice-status-transition | 5/6 pass | 6/6 pass | Fixed missing failing test |
| order-hold-reason | 3/4 pass | 4/4 pass | OK |
| catalog-suggest-latency | 2/4 pass | 4/4 pass | OK |
| notification-feed-stale | 2/3 pass | 3/3 pass | Fixed test isolation |
| workspace-label-propagation | 3/5 pass | 5/5 pass | OK |

All SOLUTION.md files contain required sections (root cause, investigation, reference impl, wrong alternatives, AI failure modes, edge cases, verification, complexity, Expected Event Timeline, positive/negative/recovery signals, Rubric A–G, Interviewer Observations, 4 defend questions). No `challenge.json` eval files touched.
