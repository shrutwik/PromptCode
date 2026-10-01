# PromptCode Challenges

This directory contains two kinds of challenges:

1. **Platform evaluation challenges** — folders that include a `challenge.json` (plus `sample_solution.py`). These are LLM-evaluation tasks for the PromptCode platform.
2. **AI-assisted interview simulation challenges** — the ten folders listed in the table below. Each includes production-like source, tests, a candidate `README.md`, and an interviewer-only `SOLUTION.md`.

## Interview simulation challenges (Medium)

| # | Slug | Type | Stack | Focus (no spoilers) |
|---|------|------|-------|---------------------|
| 1 | `invoice-status-transition` | Backend bug fix | TypeScript / Node (vitest) | Invoice status transitions under an informal billing ticket |
| 2 | `order-hold-reason` | Backend feature | Python / FastAPI (pytest) | Add hold reason through persistence and API (Part A/B) |
| 3 | `catalog-suggest-latency` | Performance / scale | TypeScript / Node (vitest) | Speed up product suggest with measurable latency/scan budgets |
| 4 | `notification-feed-stale` | Frontend state bug | React / TypeScript (vitest) | Notification unread state after mark-as-read |
| 5 | `workspace-label-propagation` | Full-stack feature | React + Express (vitest) | Labels from persistence → API → UI (Part A/B/C) |
| 6 | `shipment-csv-merge` | Data-processing bug | Python (pytest) | Merge multi-day shipment event CSVs correctly |
| 7 | `tenant-document-acl` | Authz / multi-tenant | Python / FastAPI (pytest) | Document access across tenants |
| 8 | `webhook-delivery-retry` | Async / retry | TypeScript / Node (vitest) | Webhook retries, side effects, and batch delivery |
| 9 | `pricing-rule-extract` | Behavior-preserving refactor | TypeScript (vitest) | Extract pricing helper without changing quotes |
| 10 | `subscription-proration-boundary` | Looks-correct prod bug | Python (pytest) | Cancel/proration timing when public tests already pass |

Each interview folder is self-contained. Follow that folder’s **Getting started** section to install dependencies and run tests.

Interviewer materials live in `SOLUTION.md` (root cause, reference fix, AI failure modes, rubric, defend-your-code). Do not share `SOLUTION.md` with candidates.
