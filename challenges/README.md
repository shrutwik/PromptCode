# PromptCode Challenges

This directory contains two kinds of challenges:

1. **Platform evaluation challenges** — folders that include a `challenge.json` (plus `sample_solution.py`). These are LLM-evaluation tasks for the PromptCode platform.
2. **AI-assisted interview simulation challenges** — the twenty-five folders listed below. Each includes runnable source, tests, a candidate `README.md`, and an interviewer-only `SOLUTION.md`.

## Existing interview simulation challenges

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

These ten now include investigation/verification checkpoints, an optional discussion extension, and stronger regression checks. Their original incident defects remain intentional.

## Original progressive additions

| # | Slug | Stack | Underlying problem |
|---|---|---|---|
| 11 | `warehouse-route-planner` | Python (pytest) | Routing state changes when a badge unlocks a gate |
| 12 | `courier-payment-ledger` | Python (pytest) | Per-record precision, payment identity and distinct-driver activity |
| 13 | `worker-job-dispatch` | Python (pytest) | Readiness time and worker selection are different orderings |
| 14 | `bounded-recency-cache` | Python (pytest) | Recency invariants and atomic read/compute/write |
| 15 | `service-impact-analysis` | Python (pytest) | Path boundaries and reverse dependency closure |
| 16 | `unique-word-selection` | Python (pytest) | Legal output is distinct from optimal output |
| 17 | `expression-cost-analysis` | Python (pytest) | Fixture validity, aliases, liveness and semantics-preserving optimization |
| 18 | `room-reservation-scheduler` | Python (pytest) | Half-open intervals and atomic search/commit |
| 19 | `card-triple-strategy` | Python (pytest) | Physical-card identity precedes strategy evaluation |
| 20 | `structured-event-logger` | Python (pytest) | Severity, event snapshots and explicit sink failure policy |

Each new question has three checkpoints within one platform ticket, eight visible fixtures and eight independent server observation cases. Difficulty/time metadata is provisional until calibrated with mock sessions. These are original exercises inspired by public formats; they are not copied employer repositories or authenticated employer questions. See [research and implementation notes](/Users/shrutwik/Desktop/PromptCode/docs/interview-library-expansion.md).

Each interview folder is self-contained. Follow that folder’s **Getting started** section to install dependencies and run tests.

Interviewer materials live in `SOLUTION.md` (root cause, reference fix, AI failure modes, rubric, defend-your-code). Do not share `SOLUTION.md` with candidates.

## Ranked top-twenty completion

The library now features the exact overall top twenty from the reviewed scorecard; five additional working exercises remain available. The [ranked implementation report](/Users/shrutwik/Desktop/PromptCode/docs/interview-top20-implementation.md) and [selection manifest](/Users/shrutwik/Desktop/PromptCode/docs/interview-top20-manifest.json) record the selection.

| Added family | Stack | Underlying problem |
|---|---|---|
| `canvas-document-editor` | React / TypeScript | Document identity, coordinate transforms and committed history |
| `extensible-hand-comparison` | Python | Parsing, physical identity and configurable comparison keys |
| `runway-event-scheduler` | Python | Eligibility before priority, closures and cancellation boundaries |
| `movie-search-routing` | React / Express | Shared query semantics, direct browser routes and stale responses |
| `transactional-wallet-transfer` | Python / FastAPI / SQLite | Durable atomic writes and payload-bound retries |
