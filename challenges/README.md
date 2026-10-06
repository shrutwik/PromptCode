# PromptCode Challenges

This directory contains two kinds of challenges:

1. **Platform evaluation challenges** — folders that include a `challenge.json` (plus `sample_solution.py`). These are LLM-evaluation tasks for the PromptCode platform.
2. **AI-assisted interview simulation challenges** — the ten folders listed in the table below. Each includes the service, tests, a candidate `README.md`, and an interviewer-only `SOLUTION.md`.

## Interview simulation challenges (Medium)

| # | Slug | Type | Stack | Focus (no spoilers) |
|---|------|------|-------|---------------------|
| 1 | `invoice-status-transition` | Billing incident | TypeScript / Node (vitest) | Paid invoice returned to draft before close |
| 2 | `order-hold-reason` | Orders change | Python / FastAPI (pytest) | Hold reason through the API, legacy rows stay null |
| 3 | `catalog-suggest-latency` | Search performance | TypeScript / Node (vitest) | Same suggest ranking inside a latency and scan budget |
| 4 | `notification-feed-stale` | Feed consistency | React / TypeScript (vitest) | Unread badge against concurrent mark-as-read |
| 5 | `workspace-label-propagation` | Labels across the stack | React + Express (vitest) | Workspace labels from save through API to the screen |
| 6 | `shipment-csv-merge` | Shipment merge | Python (pytest) | Multi-file shipment timelines and quantities |
| 7 | `tenant-document-acl` | Tenant isolation | Python / FastAPI (pytest) | Cross-tenant document read and update |
| 8 | `webhook-delivery-retry` | Webhook delivery | TypeScript / Node (vitest) | Retry side effects and bounded flush |
| 9 | `pricing-rule-extract` | Pricing refactor | TypeScript (vitest) | Extract the rule loop without moving a cent |
| 10 | `subscription-proration-boundary` | Proration boundary | Python (pytest) | Cancel credit at the exact period end |

Each interview folder is self-contained. Follow that folder’s **Getting started** section to install dependencies and run tests.

Interviewer materials live in `SOLUTION.md` (root cause, reference fix, AI failure modes, rubric, defend-your-code). Do not share `SOLUTION.md` with candidates.
