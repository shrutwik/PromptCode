# AI-assisted interview questions and starter codebases

> Historical research/ranking snapshot before the October 7 expansion. For the implemented twenty-question library and verified coverage, see [the implementation report](interview-library-expansion.md).

Research checked: October 7, 2026. Scope: software engineering interviews in which candidates may use an AI coding assistant.

Expanded research: [38-exercise deep dive with 224 original test scenarios](/Users/shrutwik/Desktop/PromptCode/docs/ai-assisted-interview-deep-dive.md), [exact local tests and 62 trusted probes](/Users/shrutwik/Desktop/PromptCode/docs/ai-assisted-interview-local-tests.md), and [structured JSON catalogue](/Users/shrutwik/Desktop/PromptCode/docs/ai-assisted-interview-catalogue.json). This original bank retains its initial 30 exercise numbers; new exercises 31–38 are in the deep dive.

This is a targeted review of publicly accessible company guidance, candidate accounts, and discussions across Reddit, LeetCode Discuss, Glassdoor, Hacker News, and interview-platform blogs. It is not an exhaustive internet census. Company attribution describes the linked account, not a guaranteed current interview format.

There are **30 exercises** below: **20 proposed exercises** and **10 existing PromptCode challenges**. All candidate prompts, module names, acceptance tests, time budgets, and extensions proposed here are original practice specifications. The research establishes their inspiration; it does not establish the exact starter repository or complete question used by an employer. Proposed codebases are specifications, not implemented repositories.

## What the sources actually establish

| Source | Evidence type | Observation supported by the source |
|---|---|---|
| [Canva engineering guidance](https://www.canva.dev/blog/engineering/yes-you-can-use-ai-in-our-interviews/) | Official, June 11, 2025 | Candidates are expected to use AI for realistic engineering tasks. The article illustrates its approach with an airport-control problem and emphasizes reviewing generated code. |
| [Meta E4 candidate account](https://www.reddit.com/r/leetcode/comments/1p35b98/meta_e4_software_product_interview_experience/) | Anonymous firsthand report | A staged maze codebase involved graph serialization, walls, portals, and BFS. Its separate banking OA is not established as AI-assisted. |
| [Microsoft SDE2 candidate account](https://www.reddit.com/r/leetcode/comments/1sfgtu3/ai_assisted_coding_interview_experience_microsoft/) | Anonymous firsthand report, April 8, 2026 | A load-balancer algorithm question allowed AI; debugging and explanations mattered. A GitHub-rebuild example was recruiter guidance, not the task this person received. |
| [Amazon web-application OA account](https://www.reddit.com/r/amazonemployees/comments/1tj88m7/amazon_sde1_oa_new_format_with_an_ai_assistant/) | Anonymous firsthand report | A website preview and existing codebase contained three bugs. The reported backend choices included Node, Spring Boot, and Django. |
| [Amazon MovieDB account](https://www.reddit.com/r/amazonemployees/comments/1vhkpas/amazon_backend_oa_questions_2026_greedy_coding/) | Anonymous firsthand report, August 6, 2026 | Watchlist additions appeared successful but were missing later. Additional tasks involved rate limiting and password validation. The post also promotes a practice site. |
| [Amazon intern question on Glassdoor](https://www.glassdoor.com/Interview/You-are-given-a-full-web-application-codebase-frontend-and-backend-Identify-and-fix-bugs-including-broken-search-filter-QTN_8998301.htm) | Anonymous candidate submission; answer dated May 26, 2026 | Full-stack debugging covered search/filter behavior and URL routing, with AI used for guidance. |
| [Canva frontend candidate notes](https://www.reddit.com/r/cscareerquestionsOCE/comments/1t1jfxx/canva_interview_notes/) | Firsthand post and comment | The author built a small design editor; another commenter reports a team portal. Other rounds in the post were separate from the AI round. |
| [Atlassian discussion](https://www.reddit.com/r/leetcode/comments/1wpb4da/atlassian_ai_enabled_interview/) | Anonymous firsthand comment in indexed discussion | A commenter reports designing and demonstrating a configurable logger, with candidate-provided boilerplate. Another describes staged maze work. Replies dispute whether the logger account concerns Atlassian; employer attribution remains unverified. |
| [Rippling candidate account](https://leetcode.com/discuss/post/7649290/) | Anonymous firsthand report | The author reports AI-permitted food-delivery and card-game tasks. Other linked problems were practice recommendations, not claimed interview tasks. The post promotes a practice site. |
| [Frontend discussion](https://www.reddit.com/r/Frontend/comments/1rk9d65/frontend_interviews_in_the_age_of_ai/) | Anonymous firsthand comment | One candidate reports six requested features in an existing repository within an hour; the exact features and employer are unspecified. |
| [HackerRank interview-design guidance](https://www.hackerrank.com/blog/how-to-interview-engineers-who-use-ai-coding-assistants/) | Official platform guidance | Suggested formats include debugging generated code, explaining decisions, and adapting a build to a changed requirement. These are design suggestions, not company question reports. |
| [LinkedIn AI-usage policy](https://careers.linkedin.com/Howwehire/ai-usage) | Official policy | AI permission depends on the interview or assessment. This page does not establish a particular coding question. |

The practical pattern is **inspect existing code → clarify behavior → fix or extend it → verify → explain**. This is an inference from the accounts above, especially the [Meta maze report](https://www.reddit.com/r/leetcode/comments/1p35b98/meta_e4_software_product_interview_experience/) and [Canva guidance](https://www.canva.dev/blog/engineering/yes-you-can-use-ai-in-our-interviews/), rather than a universal employer rubric.

### Evidence labels used below

- **Reported-theme adaptation:** an original exercise based on a task theme in a firsthand account. Detailed requirements are ours.
- **Official-example adaptation:** an original exercise based on a company's published illustration; it is not confirmed as a live interview question.
- **Original practice variant:** a suggested exercise that fits the observed format, without verified company attribution.
- **Existing PromptCode:** a local exercise already present in this repository; no external company attribution is implied.

## Twenty proposed exercises

### 1. Repair a maze serializer

**Question:** A maze changes shape after saving and loading. Fix the round trip while preserving walls, cell connections, and portal identities.

**Starter codebase:** Python package with `models.py`, `codec.py`, `render.py`, `fixtures/mazes.json`, and `tests/test_codec.py`. Supply a working model and renderer plus a faulty codec.

**Acceptance:** Round trips preserve topology; malformed references fail explicitly; isolated cells survive. **Follow-up:** Introduce a backward-compatible format version.

**Evidence:** Reported-theme adaptation of the [Meta maze/serialization account](https://www.reddit.com/r/leetcode/comments/1p35b98/meta_e4_software_product_interview_experience/).

### 2. Extend a maze with shortest-path output

**Question:** Implement the minimum-length route from the entrance to the exit and return the ordered coordinates. Define unreachable behavior and deterministic tie handling.

**Starter codebase:** Reuse exercise 1, adding `solver.py` and `tests/test_solver.py`. Keep parsing and rendering already implemented.

**Acceptance:** Shortest route, cycles, unreachable exit, start equals exit, and reproducible equal-length choices. **Follow-up:** Add portals with explicitly defined traversal cost.

**Evidence:** Reported-theme adaptation of the [Meta BFS/portal account](https://www.reddit.com/r/leetcode/comments/1p35b98/meta_e4_software_product_interview_experience/).

### 3. Add keys and doors to the maze

**Question:** Extend the existing solver so collecting a key enables traversal through its matching door. Return a shortest legal route.

**Starter codebase:** Reuse the maze models, codec, and solver; add key/door fixtures and staged tests.

**Acceptance:** Revisit a position with a different inventory; multiple keys; unreachable keys; routes requiring backtracking. **Follow-up:** Add a consumable key or one-way passage.

**Evidence:** Original practice variant of the staged maze format. Keys/doors are not established by the firsthand maze report used here.

### 4. Implement deterministic load balancing

**Question:** Assign timestamped jobs to available workers. Prefer the smallest eligible worker id; queue jobs when all workers are busy. Specify tie handling before coding.

**Starter codebase:** Python `scheduler.py`, `models.py`, `clock.py`, `fixtures/jobs.json`, and `tests/test_scheduler.py`, with a slow or incorrect baseline implementation.

**Acceptance:** Simultaneous arrivals/completions, queued jobs, deterministic ties, and a large workload. **Follow-up:** Add weighted workers or cancellation.

**Evidence:** Reported-theme adaptation of the [Microsoft load-balancer account](https://www.reddit.com/r/leetcode/comments/1sfgtu3/ai_assisted_coding_interview_experience_microsoft/). The account does not publish these exact dispatch rules.

### 5. Build a configurable logging library

**Question:** Complete a logger with severity filtering, structured records, and selectable console/file destinations. Demonstrate a running consumer.

**Starter codebase:** TypeScript `logger.ts`, `config.ts`, `formatters.ts`, `sinks.ts`, `demo.ts`, and `tests/logger.test.ts`. Provide interfaces and fake sinks.

**Acceptance:** Disabled levels emit nothing; invalid configuration is rejected; a sink failure follows a documented policy. **Follow-up:** Runtime configuration changes.

**Evidence:** Reported-theme adaptation of the indexed logger comment in the [Atlassian discussion](https://www.reddit.com/r/leetcode/comments/1wpb4da/atlassian_ai_enabled_interview/). Employer attribution is disputed in replies and remains unverified.

### 6. Build a small browser design editor

**Question:** Add shapes from a toolbar, select and move them, edit their color, and save/reload a design. Keep the demo scope explicit.

**Starter codebase:** React/TypeScript `Canvas.tsx`, `Toolbar.tsx`, `Inspector.tsx`, `designStore.ts`, `serialization.ts`, and component/store tests. Supply a bootable app and an empty document model.

**Acceptance:** Moving affects only the selected shape; document state survives reload; invalid saved data is handled. **Follow-up:** Undo/redo.

**Evidence:** Reported-theme adaptation of the [Canva frontend account](https://www.reddit.com/r/cscareerquestionsOCE/comments/1t1jfxx/canva_interview_notes/). Save/reload and inspector behavior are original extensions.

### 7. Extend a team portal

**Question:** Add member search and a role editor to a team portal. Persist changes and display server validation errors.

**Starter codebase:** React + Express `MembersPage.tsx`, `MemberForm.tsx`, `api.ts`, `routes/members.ts`, `memberService.ts`, a seeded store, and request/component tests.

**Acceptance:** Edits survive reload; failed saves do not display success; invalid roles are rejected. **Follow-up:** Add invitations and permissions.

**Evidence:** Reported-theme adaptation of the team-portal comment in the [Canva discussion](https://www.reddit.com/r/cscareerquestionsOCE/comments/1t1jfxx/canva_interview_notes/). Specific portal features are original.

### 8. Fix disappearing MovieDB watchlist additions

**Question:** Adding a movie shows success, but opening the watchlist does not show it. Trace the request and repair persistence and response behavior.

**Starter codebase:** Spring Boot `WatchlistController`, `WatchlistService`, repository, entity/DTO mappings, a React watchlist page, and integration fixtures. A Django or Express edition can use the same contract.

**Acceptance:** Add then GET succeeds; duplicate additions follow a stated policy; errors propagate. **Follow-up:** Concurrent additions.

**Evidence:** Reported-theme adaptation of the [Amazon MovieDB account](https://www.reddit.com/r/amazonemployees/comments/1vhkpas/amazon_backend_oa_questions_2026_greedy_coding/).

### 9. Repair search, filters, and browser routes

**Question:** A movie list loses its filter after refresh, combines filters incorrectly, and fails when a detail URL is opened directly. Fix the affected flow.

**Starter codebase:** Reuse MovieDB with `MovieList.tsx`, `queryState.ts`, `routes.tsx`, a search controller/repository, and route/API tests.

**Acceptance:** Combined filters, encoded search text, empty results, refresh, and deep links. **Follow-up:** Pagination preserves the same query.

**Evidence:** Reported-theme adaptation of the [Amazon Glassdoor question](https://www.glassdoor.com/Interview/You-are-given-a-full-web-application-codebase-frontend-and-backend-Identify-and-fix-bugs-including-broken-search-filter-QTN_8998301.htm). The movie domain and precise failures are original.

### 10. Repair a per-user rate limiter

**Question:** One busy user exhausts the allowance for other users, and requests at the reset boundary behave incorrectly. Restore the documented policy.

**Starter codebase:** Reuse MovieDB with rate-limit middleware, a store interface, fake clock, and request tests.

**Acceptance:** Independent users, exact window boundary, concurrent requests, and the expected 429 response. **Follow-up:** Explain the changes required for multiple servers.

**Evidence:** Reported-theme adaptation of the rate-limiting task mentioned in the [Amazon MovieDB account](https://www.reddit.com/r/amazonemployees/comments/1vhkpas/amazon_backend_oa_questions_2026_greedy_coding/). These failure scenarios are original.

### 11. Make password validation consistent

**Question:** Registration and password-change endpoints enforce different length rules. Apply the documented policy consistently without changing successful existing flows.

**Starter codebase:** Reuse MovieDB's auth controller, shared validator, request schemas, service, and endpoint tests.

**Acceptance:** Minimum and maximum boundaries, absent values, consistent errors, and successful valid requests. **Follow-up:** Define the policy for Unicode length.

**Evidence:** Reported-theme adaptation of the validation work mentioned in the [Amazon MovieDB account](https://www.reddit.com/r/amazonemployees/comments/1vhkpas/amazon_backend_oa_questions_2026_greedy_coding/).

### 12. Calculate delivery costs and outstanding pay

**Question:** Register drivers and deliveries, calculate total delivery cost, and mark deliveries through a cutoff as paid. Report outstanding cost.

**Starter codebase:** TypeScript `drivers.ts`, `deliveries.ts`, `costCalculator.ts`, `paymentLedger.ts`, `clock.ts`, and tests with overlapping deliveries and integer-money fixtures.

**Acceptance:** Repeated payment runs, cutoff boundaries, unknown drivers, and exact rounding. **Follow-up:** Report peak simultaneously active drivers.

**Evidence:** Reported-theme adaptation of the food-delivery task in the [Rippling firsthand account](https://leetcode.com/discuss/post/7649290/). The account names the theme; these accounting requirements are ours.

### 13. Extend a card-game engine

**Question:** Implement hand comparison using a supplied ranking specification, then add an alternate rule set without breaking the existing game.

**Starter codebase:** Python `card.py`, `hand.py`, `rules.py`, `game.py`, deterministic deck fixtures, and `tests/test_rules.py`. Give card identities and ranking rules explicitly.

**Acceptance:** Ties, duplicate-card rejection, rank boundaries, and unchanged original rules. **Follow-up:** Compare rule sets over a seeded simulation.

**Evidence:** Reported-theme adaptation of the card-game task in the [Rippling account](https://leetcode.com/discuss/post/7649290/). Hand comparison is an original choice of scope, not a recovered question statement.

### 14. Add a staged dashboard feature set

**Question:** Extend an existing dashboard with search, status filtering, sorting, pagination, a detail drawer, and saved view settings. Clarify interactions before coding.

**Starter codebase:** React `Dashboard.tsx`, `Table.tsx`, `FilterBar.tsx`, `DetailDrawer.tsx`, `viewState.ts`, mock API, and component/request tests.

**Acceptance:** Features compose; filter changes reset pagination; saved settings reload; empty/error states work. **Follow-up:** Prevent older requests overwriting newer results.

**Evidence:** Reported-theme adaptation of the six-feature repository task in the [frontend discussion](https://www.reddit.com/r/Frontend/comments/1rk9d65/frontend_interviews_in_the_age_of_ai/). The dashboard and six particular features are invented.

### 15. Extend an LRU cache with expiration

**Question:** Add TTL to an existing LRU cache while maintaining its documented capacity and access-order behavior. State expiration and refresh semantics.

**Starter codebase:** Python `cache.py`, `clock.py`, `tests/test_cache.py`, and a working non-expiring baseline.

**Acceptance:** Expiry boundary, replacement, expired-capacity reclamation, and ordering after misses. **Follow-up:** Concurrent access.

**Evidence:** Original practice variant. Some public roundups attribute this family to employers, but this bank does not rely on those attributions.

### 16. Repair verification-code expiration and reuse

**Question:** Verification succeeds at the exact expiry instant and a previously accepted code can be reused. Repair both cases while retaining valid verification behavior.

**Starter codebase:** FastAPI `routes/verification.py`, `verification_service.py`, `token_store.py`, `clock.py`, and request tests with an in-memory store.

**Acceptance:** Expiry, one-time consumption, wrong user/code, and simultaneous attempts. **Follow-up:** Resending invalidates the old code.

**Evidence:** Original practice variant. Password-reset/verification examples appear in promotional roundups, but no strong firsthand evidence was established in this pass.

### 17. Repair wallet transfers under retries

**Question:** A retried transfer debits a wallet twice; a failed credit leaves money missing. Preserve balances and implement the stated retry contract.

**Starter codebase:** FastAPI `transfer_routes.py`, `transfer_service.py`, `ledger.py`, transaction-capable SQLite fixtures, and injected-failure tests.

**Acceptance:** Duplicate request ids, failure between debit and credit, insufficient funds, and conservation of money. **Follow-up:** Concurrent transfers from the same wallet.

**Evidence:** Original practice variant of repository incident debugging; no verified company attribution.

### 18. Optimize a unique-character word selector

**Question:** Select words whose combined letters contain no duplicates and maximize total length. Repair the baseline, then support larger inputs.

**Starter codebase:** Python `word_parser.py`, `selector.py`, `validator.py`, fixtures, a brute-force baseline, and correctness/performance tests.

**Acceptance:** Repetition within a word, overlap across words, duplicate words, empty inputs, and deterministic ties. **Follow-up:** Compare strategies and justify complexity.

**Evidence:** Original practice variant. The theme appears in [community discussions](https://www.reddit.com/r/leetcode/comments/1o47lk2/officially_live_metas_new_aienabled_coding_round/), but that thread's author collected others' reports; it is not treated here as firsthand confirmation of the question.

### 19. Implement an airport runway scheduler

**Question:** Coordinate takeoff and landing requests with runway exclusion, priority rules, and emergency handling. Clarify the simulation's constraints first.

**Starter codebase:** Python `aircraft.py`, `runway.py`, `scheduler.py`, `events.py`, fake clock, and a runnable simulation with event-log tests.

**Acceptance:** No conflicting runway reservations; deterministic scheduling; cancellation; documented priority behavior. **Follow-up:** Add a second runway or weather closure.

**Evidence:** Official-example adaptation of [Canva's published illustration](https://www.canva.dev/blog/engineering/yes-you-can-use-ai-in-our-interviews/). The detailed rules are original. This is a toy scheduling exercise.

### 20. Diagnose an incorrect test before changing the service

**Question:** A new test fails against a documented parser contract. Determine whether the implementation or the test is wrong, make the smallest justified correction, and add an independent regression case.

**Starter codebase:** TypeScript `parser.ts`, `schema.ts`, a short contract, correct and faulty test fixtures, and a small consumer.

**Acceptance:** Explain the disputed assumption; preserve valid parsing; reject invalid input; do not weaken assertions just to get a pass. **Follow-up:** A requirement change makes the old implementation incorrect.

**Evidence:** Original practice variant inspired by a [Meta candidate's test-alignment stage](https://www.reddit.com/r/leetcode/comments/1qxwwh5/sharing_my_meta_e6_mle_interview_experience/) and [HackerRank's debug-and-explain format](https://www.hackerrank.com/blog/how-to-interview-engineers-who-use-ai-coding-assistants/). The parser scenario is invented.

## Ten exercises already available in PromptCode

These are local exercises based on their candidate READMEs and file inventory. The acceptance cases below describe verification targets; this research pass did not run their tests or certify their current implementation. Each linked README gives setup instructions.

| # | Candidate question | Existing codebase and relevant modules | Acceptance cases |
|---|---|---|---|
| 21 | A user reads or edits another tenant's document. Repair access checks without revealing whether the document exists. | [tenant-document-acl](/Users/shrutwik/Desktop/PromptCode/challenges/tenant-document-acl/README.md): FastAPI `app/auth.py`, `app/main.py`, `app/service.py`; `tests/test_acl.py`. | Cross-tenant GET/PATCH return 404; own-tenant access succeeds; invalid tokens return 401. |
| 22 | A retried webhook records the same charge twice, and flushing a queue overloads the receiver. Repair both behaviors. | [webhook-delivery-retry](/Users/shrutwik/Desktop/PromptCode/challenges/webhook-delivery-retry/README.md): TypeScript `src/worker.ts`, `sideEffects.ts`, `retryPolicy.ts`; `tests/worker.test.ts`. | One side effect per delivery id; bounded attempts; approximately five simultaneous posts. |
| 23 | A paid invoice returns to draft and becomes editable. Enforce the existing transition contract. | [invoice-status-transition](/Users/shrutwik/Desktop/PromptCode/challenges/invoice-status-transition/README.md): TypeScript `statusMachine.ts`, `invoiceService.ts`, `api.ts`, store; `tests/statusMachine.test.ts`. | Illegal moves return 409 and preserve state; valid transitions succeed; void is terminal. |
| 24 | Canceling exactly at the billing period's end produces a credit. Repair the boundary calculation. | [subscription-proration-boundary](/Users/shrutwik/Desktop/PromptCode/challenges/subscription-proration-boundary/README.md): Python `proration/period.py`, `billing.py`, `timeutil.py`; `tests/test_proration.py`. | End is excluded; start is included; before-start cancellation gets no credit; mid-period still works. |
| 25 | Two shipment files arrive out of order and count duplicate events twice. Correct the merged timeline and quantities. | [shipment-csv-merge](/Users/shrutwik/Desktop/PromptCode/challenges/shipment-csv-merge/README.md): Python `shipment_merge/parse.py`, `merge.py`, `summarize.py`; `tests/test_merge.py`. | Timestamp order; deduplicate by event id; preserve distinct events sharing a status. |
| 26 | Concurrent mark-as-read actions lose updates and leave the unread badge stale. Repair state consistency. | [notification-feed-stale](/Users/shrutwik/Desktop/PromptCode/challenges/notification-feed-stale/README.md): React `src/feedStore.ts`, `api.ts`, `NotificationList.tsx`; `tests/feed.test.tsx`. | Badge equals unread rows; both overlapping changes survive; already-read rows remain read. |
| 27 | An order's hold reason disappears after refresh. Persist and return it while supporting legacy rows. | [order-hold-reason](/Users/shrutwik/Desktop/PromptCode/challenges/order-hold-reason/README.md): FastAPI `app/main.py`, `schemas.py`, `models.py`, `service.py`; `tests/test_orders.py`. | Hold/save/GET round trip; release returns open; legacy reason is null. |
| 28 | Ticket labels disappear after save. Carry workspace-scoped label ids through storage, API, and UI. | [workspace-label-propagation](/Users/shrutwik/Desktop/PromptCode/challenges/workspace-label-propagation/README.md): React + Express `server/app.ts`, `db.ts`, `client/api.ts`, `TicketLabels.tsx`; request/component/round-trip tests. | PUT then GET returns stored labels; foreign workspace ids return 400; UI matches server. |
| 29 | Catalog suggestions are too slow. Improve the implementation without changing result ranking. | [catalog-suggest-latency](/Users/shrutwik/Desktop/PromptCode/challenges/catalog-suggest-latency/README.md): TypeScript `src/suggest.ts`, `rank.ts`, `indexCache.ts`, `queryCounter.ts`; `tests/suggest.test.ts`. | Score/popularity/id order preserved; supplied 10,000-product case stays below 200 ms and 20,000 scans. |
| 30 | Extract the pricing-rule loop without changing any quoted amount or rule-order behavior. | [pricing-rule-extract](/Users/shrutwik/Desktop/PromptCode/challenges/pricing-rule-extract/README.md): TypeScript `src/pricingEngine.ts`, `rules.ts`, `money.ts`; `tests/pricing.test.ts`. | Same cents and applied codes; same half-up rounding; negative result floors at zero; empty rules preserve base. |

## How to package the codebases

The following is a suggested PromptCode authoring approach, not a reported employer requirement.

1. **Reuse small families:** One maze repository can support exercises 1–3. One MovieDB app can support 8–11. Keep separate exercise snapshots so a completed earlier task is not required to start another.
2. **Match local challenge structure:** Candidate `README.md`, runnable source, fixtures, tests, and separate interviewer-only `SOLUTION.md`, as described in [challenges/README.md](/Users/shrutwik/Desktop/PromptCode/challenges/README.md). Keep solution material outside candidate delivery.
3. **Supply enough working behavior:** For debugging, begin with a runnable app and focused defects. For feature work, supply interfaces and surrounding behavior. Avoid setup friction dominating the assessment.
4. **Stage the work:** Baseline diagnosis, core correction/feature, then an edge case or changed requirement. Suggested budgets are 45–60 minutes for a focused incident and 60–90 minutes for a staged build; calibrate using actual mock runs.
5. **Control nondeterminism:** Fake clocks, seeded decks, fixed fixtures, mock external services, and transaction fixtures make failures reproducible. Use operation counts alongside timing for performance checks.
6. **Separate correctness from process:** Check behavior with trusted tests and inspect the candidate's understanding, AI-output review, debugging, and explanation. A particular amount of AI usage is not by itself evidence of ability.

Suggested defend questions for any exercise:

- Which files did you inspect first, and what did they establish?
- What requirement did you clarify before implementing?
- Which AI suggestion did you verify, change, or reject, and why?
- Show a test that catches the original failure and a test that protects existing behavior.
- Explain one function you changed without asking the assistant to explain it for you.
- What happens under duplicate, concurrent, malformed, or boundary input?
- How would the solution change under a larger workload or a new constraint?

## Recommended first additions

Based on source specificity, variety beyond the current library, and starter-code reuse, prioritize **maze exercises 1–3**, **MovieDB exercises 8–11**, **logger 5**, **design editor 6**, and **delivery costs 12**. This ordering is an editorial recommendation, not a measured question-frequency ranking.

## Limits and research exclusions

- Public reports are self-selected and sometimes promotional. Multiple reposts of one experience are not independent corroboration.
- The exact employers' private repositories were not obtained. All proposed starter structures are ours.
- Some Microsoft accounts describe algorithms while others describe repositories. Do not assume one uniform company format from these accounts.
- A [Meta report of implementing 2D convolution](https://www.reddit.com/r/leetcode/comments/1reuwrd/meta_ai_coding_interview/) explicitly distinguishes “AI coding” from “AI-enabled coding.” It is not included as confirmed AI-assisted evidence.
- [Hacker News discussions](https://news.ycombinator.com/item?id=47415117) provide useful format debates, but did not establish additional specific questions used in this bank.
- Commercial roundups mentioning compiler inference, card strategies, wallet bugs, or password resets were not promoted to verified employer questions without stronger evidence.
- LinkedIn's [official policy](https://careers.linkedin.com/Howwehire/ai-usage) makes permission interview-specific. Keep permission and tool availability in each exercise's candidate instructions.

## Research checkpoint

- **Need:** A sourced question list with the codebase each exercise requires.
- **References:** Public sources linked above; local challenge index, candidate READMEs, and module inventory.
- **Change:** This research document only. No proposed starter codebase was implemented.
- **Verification:** Verified consecutive numbering for all 30 exercises, required specification fields for all 20 proposals, 11 local file links, and 42 named local module/test paths. Supporting web pages or indexed source excerpts were reviewed; this is not an automated availability check of every external link. No application tests were run for this documentation-only addition.
