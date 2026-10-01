# Medium Interview Challenges — Audit Summary

Audit date: 2026-09-18  
Method: install deps, run documented test commands, verify starter failures, apply SOLUTION transiently, restore starter, calibrate Medium 25–35m, confirm SOLUTION sections + AI trap + irrelevant noise file.

| Challenge | Starter tests | Reference tests | Difficulty | AI trap | Changes made |
|-----------|---------------|-----------------|------------|---------|--------------|
| invoice-status-transition | `npm test` — 5 pass / 1 fail (`paid→draft`) | 6/6 pass after removing paid special-case | Medium 25–30 | Ticket blames timezone; AI patches `timezoneFormat.ts` first | Added failing regression test; README acceptance wording |
| order-hold-reason | `.venv` `pytest -q` — 3/1 (`hold_reason` missing) | 4/4 after `to_public_dict` field | Medium 25–30 | Over-validate `hold_reason` as required string | None (already correct) |
| catalog-suggest-latency | `npm test` — 2/2 (latency + scans) | 4/4 after single-pass scan fix | Medium 25–35 | Cache/`indexCache` without fixing O(n²) | None |
| notification-feed-stale | `npm test` — 2/1 (concurrent mark-as-read) | 3/3 after removing stale snapshot | Medium 25–30 | Fix list keys only; leave store race | `afterEach(cleanup)` test isolation |
| workspace-label-propagation | `npm test` — 3/2 (API + UI labelIds) | 5/5 after API+UI wire-up | Medium 30–35 | Free-text tags or API-only fix | None |
| shipment-csv-merge | `.venv` `pytest -q` — 2/2 (dedupe/qty) | 4/4 after event_id dedupe | Medium 25–35 | Dedupe by `(shipment_id,status)` | None |
| tenant-document-acl | `.venv` `pytest -q` — 3/2 (cross-tenant) | 5/5 after tenant check → 404 | Medium 25–30 | 403 oracle leak or GET-only fix | None |
| webhook-delivery-retry | `npm test` — 1/2 (charge + concurrency) | 3/3 after success-path charge + pool | Medium 30–35 | Header-only / unbounded `Promise.all` | None |
| pricing-rule-extract | `npm test` — 5/0 (green by design) | 5/5 after real `applyRules` extract | Medium 25–30 | Reorder rules / change rounding | None |
| subscription-proration-boundary | `.venv` `pytest -q` — 4/0 (green by design) | 4/4 + hidden half-open case | Medium 25–35 | Patch display timezone red herring | None |

## Cross-cutting

- All 10 `SOLUTION.md` files include required sections: root cause, investigation path, reference impl, wrong alternatives, AI failure modes, edge cases, verification, complexity, Expected Event Timeline, positive/negative/recovery signals, Rubric A–G /100, Interviewer Observations, 4 defend questions + guides.
- Each challenge has ≥1 unlabeled irrelevant/noise file and ≥1 AI trap documented only in SOLUTION.
- Starters left in interview-ready buggy (or green-by-design) state after reference verification.
- No `challenge.json` eval challenges modified.
- Detail notes: `challenges/_audit_batch_a.md`, `challenges/_audit_batch_b.md`.

## Ops note

Use per-challenge `.venv` for Python challenges — global pytest can crash on langsmith/pydantic plugin conflicts.
