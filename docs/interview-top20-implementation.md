# Ranked top twenty: implementation checkpoint

> The [October 8 refinement](interview-top20-refinement.md) adds structured parts and pressure checks. This report preserves the earlier implementation checkpoint.

Implemented October 7, 2026. This completes the **overall top twenty** from the reviewed weighted scorecard. The earlier expansion contained twenty available exercises but omitted five high-ranked families. Those five are now authored and registered; all working content remains, for **twenty featured + five additional exercises**. The selection is explicit in [the manifest](interview-top20-manifest.json), with a regression check against the original ranking. Editorial scores are unchanged selection judgments, not candidate grades or measured hiring validity.

## Featured selection

| Rank | Exercise | Original selection score | Stack |
|---|---|---:|---|
| 1 | [Warehouse routes](/Users/shrutwik/Desktop/PromptCode/challenges/warehouse-route-planner/README.md) | 93 | Python |
| 2 | [Webhook retry](/Users/shrutwik/Desktop/PromptCode/challenges/webhook-delivery-retry/README.md) | 91 | TypeScript / Node |
| 3 | [Courier payments](/Users/shrutwik/Desktop/PromptCode/challenges/courier-payment-ledger/README.md) | 88 | Python |
| 4 | [Document access](/Users/shrutwik/Desktop/PromptCode/challenges/tenant-document-acl/README.md) | 85 | Python / FastAPI |
| 5 | [Worker dispatch](/Users/shrutwik/Desktop/PromptCode/challenges/worker-job-dispatch/README.md) | 84 | Python |
| 6 | [Search suggest](/Users/shrutwik/Desktop/PromptCode/challenges/catalog-suggest-latency/README.md) | 83 | TypeScript / Node |
| 7 | [Bounded cache](/Users/shrutwik/Desktop/PromptCode/challenges/bounded-recency-cache/README.md) | 82 | Python |
| 8 | [Unique word selection](/Users/shrutwik/Desktop/PromptCode/challenges/unique-word-selection/README.md) | 81 | Python |
| 9 | [Service impact](/Users/shrutwik/Desktop/PromptCode/challenges/service-impact-analysis/README.md) | 81 | Python |
| 10 | [Canvas editor](/Users/shrutwik/Desktop/PromptCode/challenges/canvas-document-editor/README.md) | 80 | React / TypeScript |
| 11 | [Shipment CSV](/Users/shrutwik/Desktop/PromptCode/challenges/shipment-csv-merge/README.md) | 80 | Python |
| 12 | [Expression analysis](/Users/shrutwik/Desktop/PromptCode/challenges/expression-cost-analysis/README.md) | 77 | Python |
| 13 | [Structured logger](/Users/shrutwik/Desktop/PromptCode/challenges/structured-event-logger/README.md) | 77 | Python |
| 14 | [Hand comparison](/Users/shrutwik/Desktop/PromptCode/challenges/extensible-hand-comparison/README.md) | 76 | Python |
| 15 | [Room reservations](/Users/shrutwik/Desktop/PromptCode/challenges/room-reservation-scheduler/README.md) | 76 | Python |
| 16 | [Notification feed](/Users/shrutwik/Desktop/PromptCode/challenges/notification-feed-stale/README.md) | 76 | React / TypeScript |
| 17 | [Runway simulation](/Users/shrutwik/Desktop/PromptCode/challenges/runway-event-scheduler/README.md) | 75 | Python |
| 18 | [Search and routes](/Users/shrutwik/Desktop/PromptCode/challenges/movie-search-routing/README.md) | 75 | React / Express / TypeScript |
| 19 | [Invoice status](/Users/shrutwik/Desktop/PromptCode/challenges/invoice-status-transition/README.md) | 74 | TypeScript / Node |
| 20 | [Wallet transfers](/Users/shrutwik/Desktop/PromptCode/challenges/transactional-wallet-transfer/README.md) | 73 | Python / FastAPI / SQLite |

The retained additional exercises are order hold, ticket labels, pricing extraction, proration and sum-15 card triples. Nothing is deleted or relabeled as an employer-private question.

## Five missing families completed

- **Canvas editor:** runnable React/SVG document editor with selection, zoomed movement, styling, JSON save/load, validation, completed-action history and outside-surface release. Eight visible tests include rendered interactions; eight independent state probes and an explicit rendered-review requirement.
- **Hand comparison:** full-rank parsing, physical-card validation, category/tie keys and supplied rule precedence. This is the defined three-card mini-game, with eight visible tests and eight independent probes.
- **Runway simulation:** arrived-first eligibility, priority, non-preemption, half-open closures and waiting cancellations. Delay through a closure re-evaluates readiness. Eight visible tests and eight independent probes; a toy interview model.
- **Search and routing:** React/Express query composition, stable sort/paging, literal query round trips, URL hydration, direct routes, detail/404 and stale-request rejection. Vite browser preview proxies API calls to the supplied local Express launcher. Eight visible tests include rendered and HTTP integration; eight independent helper/HTTP probes and an explicit rendered-review requirement.
- **Wallet transfers:** durable SQLite balance/receipt transaction, immutable stored replay result, payload conflicts, rollback at two failure points and concurrent independent connections. Includes a FastAPI endpoint and eight visible/independent cases each.

Each candidate starter retains an intentional contract defect. Reviewed solutions and wrong-repair fixtures are server/test-only in `backend/tests/ranked_reference_fixtures.py`; expected grading results stay outside candidate execution. Specific interviewer questions address the underlying model rather than just a green result.

## Website and runner integration

- Registry version 3 contains 25 records; the exact featured twenty come first and have ranks 1–20. Five additional records remain available. Candidate cards and progress cards expose optional `featured_rank`; the website displays “Core #N” or “More practice.”
- Every exercise has one platform ticket, even when its brief contains working checkpoints.
- Behavioral inventory version `behavioral-2026-10-v4` has 182 probes: 62 original + 80 first expansion + 40 ranked additions. Version changes invalidate prior result bindings without recalculating historical scores.
- The two new Node exercises reuse the existing reviewed React/Express lock graph. Local Docker QA adds those exact dependencies at their per-slug image paths. The standard Node Docker build already discovers all challenge package locks and must be rebuilt/published during release; no per-candidate dependency installation is added.
- Python wallet dependencies match the canonical backend lock. No new external service is required.

## Verification

Final inventory: twenty featured, twenty-five available, 195 named visible tests and 182 independent probes. All local report links exist; every solution guide has four specific review questions.

- **Isolated Docker QA:** all 154 checks completed successfully across the full run and the targeted rerun of the two frontend suites after their browser-environment configuration fix. This covers all 25 starters and reviewed repairs, selected baseline/edge wrong repairs, all reference visible suites and evaluator integrity. All 182 independent probes pass on the reviewed references.
- **Authoring/integration QA:** 84 passed, covering 13 Python expansion references and their wrong repairs plus task, API, catalogue, calibration and publication checks. The final five ranked families passed a further targeted isolated rerun (25 checks) after their starter checkpoints and invalid-input contract were finalized. Three additional tests protect the exact top-twenty selection, card metadata and retention of the original exercises.
- **Publication/smoke:** static gate passes all 25; website-service smoke reports 25 and creates a session workspace. Frontend catalogue scripts pass syntax checks. Both new React exercises pass TypeScript checks and production Vite builds in the isolated runner. The existing challenge-page browser-script tests also pass (3); asset versions were advanced for the rank labels.

This is a local implementation, not a production deployment. New estimated time boxes and difficulty labels remain provisional pending mock-interview calibration; the declared rendered/source/performance review requirements remain release obligations. See the [initial source review](interview-library-expansion.md) for research coverage and access limits.
