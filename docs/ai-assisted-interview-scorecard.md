# Criteria-based question rankings

> Historical research/ranking snapshot before the October 7 expansion. For the implemented twenty-question library and verified coverage, see [the implementation report](interview-library-expansion.md).

Review date: October 7, 2026. This scorecard replaces the earlier qualitative order for numerical ranking. **36 question families** cover all **38 research exercise IDs**, with maze exercises 1–3 combined into one staged family. It scores **26 new families and all ten existing questions**, including options excluded from the earlier shortlist, so the exclusions can be evaluated rather than assumed.

These are explicit editorial ratings of the described scope, not measured hiring frequency, employer authenticity, completion rates, calibrated difficulty or statistical estimates. A score of 85 does not mean an 85% success rate. No private tests or production state were newly verified. Ratings can change after implementation or mock-session evidence.

## Criteria, weights and anchors

| Criterion | Weight | 1 | 3 | 5 |
|---|---:|---|---|---|
| D — Engineering depth with AI available | 30% | Trivial generation/change | Focused correction or algorithm with meaningful edges | Interacting systems/stages require modeling, verification and explanation |
| V — Distinct coverage | 25% | Mostly duplicates existing skills | Useful variation with substantial overlap | Introduces a missing skill family |
| E — Research support | 15% | Original proposal with no external question match | Firsthand reported theme or official illustrative example | Officially verified interview question with a complete published contract |
| G — Fair, reproducible grading | 20% | No defensible objective check | Material oracle, UI, semantic or quality-metric review burden | Clear contract and independent deterministic oracle are feasible |
| F — Delivery readiness / lower effort | 10% | Major unfamiliar platform work | New focused scaffold using familiar runtimes | Existing scaffold, tests and runner/evaluator wiring |

All ratings are 1–5; **higher is better**, including F. A 2 or 4 is an intermediate judgment. E=2 includes detailed public practice or documented local questions without a verified employer-question match; E=4 means a firsthand theme plus a compatible detailed practice example, not independently authenticated employer content. No family receives E=5. A documented practice page is evidence for its own exercise only.

V is measured against the current ten for new questions; for an existing question, it is measured against the other nine, avoiding the circular penalty of comparing a question with itself. It does not automatically discount overlap between two new families: catalogue curation must consider that separately. For example, a card strategy and a hand comparator can both score well but need not both be immediate additions.

G measures the defensibility of grading the full described exercise, including extensions; F measures authoring/readiness effort. Existing scaffold availability does not certify its release. For new questions, G is projected feasibility, not a claim that a grader already exists. Grades reflect the scopes in the [research catalogue](/Users/shrutwik/Desktop/PromptCode/docs/ai-assisted-interview-catalogue.json).

**Weighted score /100 = 6D + 5V + 3E + 4G + 2F.** This is a linear decision aid with a theoretical minimum of 20 and maximum of 100. For example, staged maze (5,5,4,5,3) scores 30+25+12+20+6=93. Equal totals are substantively tied; table order breaks ties by D,V,G,E,F descending and original ID ascending. Do not interpret adjacent small differences as reliable evidence of superiority.

The linked [previous recommendation](/Users/shrutwik/Desktop/PromptCode/docs/ai-assisted-interview-priorities.md) was holistic. Making weights explicit changes some positions: deterministic graph/search families rise, redundant CRUD falls, and broad UI/strategy builds carry their grading/effort cost. Weights were chosen before calculating totals; they are proposed product priorities, not externally established standards.

## Full overall ranking

| Rank | Question family | Status | D | V | E | G | F | Score /100 | Quality rank without F |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Staged maze | New | 5 | 5 | 4 | 5 | 3 | 93 | 1 |
| 2 | Webhook retry | Existing | 5 | 5 | 2 | 5 | 5 | 91 | 3 |
| 3 | Delivery accounting | New | 5 | 4 | 4 | 5 | 3 | 88 | 2 |
| 4 | Tenant document access | Existing | 4 | 5 | 2 | 5 | 5 | 85 | 7 |
| 5 | Two-heap load balancer | New | 4 | 5 | 3 | 5 | 3 | 84 | 4 |
| 6 | Catalog suggestions | Existing | 5 | 5 | 2 | 3 | 5 | 83 | 10 |
| 7 | Progressive LRU cache | New | 5 | 4 | 2 | 5 | 3 | 82 | 5 |
| 8 | Maximum unique-character subset | New | 4 | 5 | 2 | 5 | 3 | 81 | 8 |
| 9 | Service dependency impact | New | 4 | 5 | 2 | 5 | 3 | 81 | 9 |
| 10 | Canvas editor | New | 5 | 5 | 3 | 3 | 2 | 80 | 6 |
| 11 | Shipment CSV merge | Existing | 4 | 4 | 2 | 5 | 5 | 80 | 14 |
| 12 | Compiler cost and optimization | New | 5 | 5 | 2 | 3 | 2 | 77 | 11 |
| 13 | Configurable logger | New | 4 | 5 | 2 | 4 | 3 | 77 | 12 |
| 14 | Extensible hand comparison | New | 4 | 4 | 2 | 5 | 3 | 76 | 15 |
| 15 | Meeting scheduler | New | 4 | 4 | 2 | 5 | 3 | 76 | 16 |
| 16 | Notification feed | Existing | 4 | 4 | 2 | 4 | 5 | 76 | 21 |
| 17 | Toy runway scheduler | New | 5 | 4 | 3 | 3 | 2 | 75 | 13 |
| 18 | Search, filters and routing | New | 4 | 4 | 3 | 4 | 3 | 75 | 17 |
| 19 | Invoice transitions | Existing | 3 | 4 | 2 | 5 | 5 | 74 | 22 |
| 20 | Transactional wallet transfers | New | 5 | 4 | 1 | 4 | 2 | 73 | 18 |
| 21 | Crawler frontier and cooldown | New | 5 | 3 | 2 | 4 | 3 | 73 | 19 |
| 22 | Sum-15 card strategy | New | 4 | 5 | 2 | 3 | 3 | 73 | 20 |
| 23 | Contained-string progression | New | 3 | 4 | 2 | 5 | 4 | 72 | 23 |
| 24 | Workspace ticket labels | Existing | 4 | 3 | 2 | 4 | 5 | 71 | 26 |
| 25 | Per-user rate limiter | New | 4 | 3 | 3 | 4 | 3 | 70 | 24 |
| 26 | Pricing extraction | Existing | 3 | 4 | 2 | 4 | 5 | 70 | 27 |
| 27 | Proration boundary | Existing | 3 | 3 | 2 | 5 | 5 | 69 | 29 |
| 28 | Friend recommendation | New | 4 | 5 | 2 | 2 | 2 | 67 | 25 |
| 29 | Expense rules and trip aggregation | New | 4 | 2 | 2 | 5 | 3 | 66 | 28 |
| 30 | Test-contract diagnosis | New | 3 | 3 | 3 | 4 | 4 | 66 | 30 |
| 31 | Six-feature dashboard | New | 4 | 3 | 2 | 3 | 2 | 61 | 31 |
| 32 | Watchlist persistence | New | 3 | 1 | 3 | 5 | 3 | 58 | 32 |
| 33 | Order hold persistence | Existing | 2 | 2 | 2 | 5 | 5 | 58 | 34 |
| 34 | Verification expiry and reuse | New | 3 | 2 | 1 | 5 | 3 | 57 | 33 |
| 35 | Password policy consistency | New | 2 | 1 | 3 | 5 | 4 | 54 | 36 |
| 36 | Team portal | New | 3 | 1 | 3 | 4 | 2 | 52 | 35 |

The quality rank removes F and divides the remaining weighted contribution by 90. It helps separate content merit from the advantage of already having a scaffold; it still includes grading feasibility. It is not a second independent assessment.

## Best twenty new research families, scored

This is the weighted top twenty among all 26 new families, rather than just re-scoring the earlier twenty. A lower-ranked option can still be valuable as a track-specific capstone or warm-up.

| New rank | Question family | D | V | E | G | F | Score /100 |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | Staged maze | 5 | 5 | 4 | 5 | 3 | 93 |
| 2 | Delivery accounting | 5 | 4 | 4 | 5 | 3 | 88 |
| 3 | Two-heap load balancer | 4 | 5 | 3 | 5 | 3 | 84 |
| 4 | Progressive LRU cache | 5 | 4 | 2 | 5 | 3 | 82 |
| 5 | Maximum unique-character subset | 4 | 5 | 2 | 5 | 3 | 81 |
| 6 | Service dependency impact | 4 | 5 | 2 | 5 | 3 | 81 |
| 7 | Canvas editor | 5 | 5 | 3 | 3 | 2 | 80 |
| 8 | Compiler cost and optimization | 5 | 5 | 2 | 3 | 2 | 77 |
| 9 | Configurable logger | 4 | 5 | 2 | 4 | 3 | 77 |
| 10 | Extensible hand comparison | 4 | 4 | 2 | 5 | 3 | 76 |
| 11 | Meeting scheduler | 4 | 4 | 2 | 5 | 3 | 76 |
| 12 | Toy runway scheduler | 5 | 4 | 3 | 3 | 2 | 75 |
| 13 | Search, filters and routing | 4 | 4 | 3 | 4 | 3 | 75 |
| 14 | Transactional wallet transfers | 5 | 4 | 1 | 4 | 2 | 73 |
| 15 | Crawler frontier and cooldown | 5 | 3 | 2 | 4 | 3 | 73 |
| 16 | Sum-15 card strategy | 4 | 5 | 2 | 3 | 3 | 73 |
| 17 | Contained-string progression | 3 | 4 | 2 | 5 | 4 | 72 |
| 18 | Per-user rate limiter | 4 | 3 | 3 | 4 | 3 | 70 |
| 19 | Friend recommendation | 4 | 5 | 2 | 2 | 2 | 67 |
| 20 | Expense rules and trip aggregation | 4 | 2 | 2 | 5 | 3 | 66 |

## Current ten, scored separately

| Existing rank | Question | D | V | E | G | F | Score /100 |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | Webhook retry | 5 | 5 | 2 | 5 | 5 | 91 |
| 2 | Tenant document access | 4 | 5 | 2 | 5 | 5 | 85 |
| 3 | Catalog suggestions | 5 | 5 | 2 | 3 | 5 | 83 |
| 4 | Shipment CSV merge | 4 | 4 | 2 | 5 | 5 | 80 |
| 5 | Notification feed | 4 | 4 | 2 | 4 | 5 | 76 |
| 6 | Invoice transitions | 3 | 4 | 2 | 5 | 5 | 74 |
| 7 | Workspace ticket labels | 4 | 3 | 2 | 4 | 5 | 71 |
| 8 | Pricing extraction | 3 | 4 | 2 | 4 | 5 | 70 |
| 9 | Proration boundary | 3 | 3 | 2 | 5 | 5 | 69 |
| 10 | Order hold persistence | 2 | 2 | 2 | 5 | 5 | 58 |

## Rationale for every criterion, every question

These notes make each assigned number reviewable. They describe the current proposed or existing exercise, not every possible richer version of that theme.

### 1. Staged maze — 93/100

Research IDs: 1, 2, 3; New.

- **D=5:** Codec, shortest paths and key-state search supply multiple interacting stages.
- **V=5:** Graph/state-space progression is absent from the ten.
- **E=4:** Firsthand maze theme and public staged practice; exact contracts remain original.
- **G=5:** BFS and tiny exhaustive-state oracles allow deterministic correctness checks.
- **F=3:** New Python scaffold and staged grading are needed; no implemented family yet.

### 2. Webhook retry — 91/100

Research IDs: 22; Existing.

- **D=5:** Retry effects, attempt bounds and bounded flush exercise interacting invariants.
- **V=5:** Unique retry-delivery system among the other nine.
- **E=2:** Documented local challenge; external employer use is not established.
- **G=5:** Six independent probes plus visible tests cover clear deterministic requirements.
- **F=5:** Implemented starter and existing runner/test wiring; not freshly release-certified.

### 3. Delivery accounting — 88/100

Research IDs: 12; New.

- **D=5:** Payments, totals, precision and distinct-driver activity interact.
- **V=4:** Adds evolving object modeling beyond existing isolated money bugs.
- **E=4:** Firsthand delivery theme and detailed public practice; not authenticated employer tests.
- **G=5:** Integer-money and interval-sweep oracles support exact outcomes.
- **F=3:** New service and event fixtures; existing runtimes can be reused.

### 4. Tenant document access — 85/100

Research IDs: 21; Existing.

- **D=4:** Read/write authorization, non-disclosure and mutation preservation.
- **V=5:** Only dedicated security-isolation ticket among the other nine.
- **E=2:** Documented local challenge, not authenticated employer question.
- **G=5:** Nine trusted probes with bidirectional isolation and rejected-state checks.
- **F=5:** Existing scaffold, fixtures and evaluator wiring.

### 5. Two-heap load balancer — 84/100

Research IDs: 4; New.

- **D=4:** Queue policy, completions and deterministic ties require event reasoning.
- **V=5:** Heap/event scheduling is absent from the current ten.
- **E=3:** Firsthand AI-permitted load-balancer report; dispatch semantics are ours.
- **G=5:** A simple independent event simulator can establish exact assignments.
- **F=3:** Focused new scaffold and heap/reference comparison tests.

### 6. Catalog suggestions — 83/100

Research IDs: 29; Existing.

- **D=5:** Optimization must preserve multi-key ranking and input behavior.
- **V=5:** Only dedicated performance ticket among the other nine.
- **E=2:** Documented local challenge; external use unknown.
- **G=3:** Five probes check output; latency/counter integrity need calibrated review.
- **F=5:** Existing workload, starter and grading hooks; review gaps remain.

### 7. Progressive LRU cache — 82/100

Research IDs: 15; New.

- **D=5:** Recency, resize and atomic creation combine data structures with concurrency.
- **V=4:** Adds a distinct cache system while sharing some concurrency concepts.
- **E=2:** Detailed public practice; TTL is a separate original extension.
- **G=5:** Fake clocks and controlled factories make invariants deterministic.
- **F=3:** New cache scaffold and thread/interleaving tests; standard Python runtime.

### 8. Maximum unique-character subset — 81/100

Research IDs: 18; New.

- **D=4:** Validator versus optimizer and exact-search scaling supply distinct stages.
- **V=5:** Adds combinatorial search beyond existing ticket debugging.
- **E=2:** Detailed public practice; no verified exact employer prompt.
- **G=5:** Exhaustive small-list oracle establishes legality and optimum independently.
- **F=3:** Focused solver/validator scaffold and generated fixtures.

### 9. Service dependency impact — 81/100

Research IDs: 34; New.

- **D=4:** Path normalization, subtree deletion and graph closure interact.
- **V=5:** Adds dependency analysis missing from current product tickets.
- **E=2:** Detailed public practice; no authenticated employer attribution.
- **G=5:** Small explicit graphs and path boundaries permit independent oracles.
- **F=3:** New Python graph/path scaffold and cases; runtime reuse.

### 10. Canvas editor — 80/100

Research IDs: 6; New.

- **D=5:** Selection, pointer coordinates, persistence and history require coherent design.
- **V=5:** No comparable open-ended graphical build in the ten.
- **E=3:** Firsthand editor account; our storage and undo extensions are original.
- **G=3:** State oracles help, but interaction and usable-output checks need browser/manual review.
- **F=2:** Substantial frontend scaffold, interaction harness and scope calibration.

### 11. Shipment CSV merge — 80/100

Research IDs: 25; Existing.

- **D=4:** Identity, sorting, quantities and snapshot reset form multiple invariants.
- **V=4:** Only batch-ingestion/deduplication family among the other nine.
- **E=2:** Documented local challenge, no employer authentication.
- **G=5:** Six independent probes with deterministic totals/order/state reset.
- **F=5:** Existing Python scaffold, fixtures and runner.

### 12. Compiler cost and optimization — 77/100

Research IDs: 33; New.

- **D=5:** Parsing, liveness, dead code and constants demand semantic understanding.
- **V=5:** Introduces language/dataflow analysis missing from the ten.
- **E=2:** Detailed public practice; exact memory/division conventions must be authored.
- **G=3:** Oracle and liveness allocation conventions are substantial grading risks until specified.
- **F=2:** New mini-language, independent interpreter and advanced fixtures.

### 13. Configurable logger — 77/100

Research IDs: 5; New.

- **D=4:** API design, copied context, reconfiguration and sink failures interact.
- **V=5:** Adds library/configuration design absent from the ten.
- **E=2:** Logger comment has disputed employer attribution; no published full prompt.
- **G=4:** In-memory sinks are objective; design/failure-policy choices require explicit rubric.
- **F=3:** Focused TypeScript scaffold, demo and failure tests.

### 14. Extensible hand comparison — 76/100

Research IDs: 13; New.

- **D=4:** Parser, comparison keys and alternate rules supply a coherent staged library.
- **V=4:** New parser/rule domain, although a second card family reduces portfolio novelty.
- **E=2:** Public comparator practice; generic card-game account does not establish exact ranking rules.
- **G=5:** Supplied finite rules enable exact exhaustive comparisons.
- **F=3:** New deck/rules fixtures and baseline comparator.

### 15. Meeting scheduler — 76/100

Research IDs: 35; New.

- **D=4:** Earliest gaps, half-open intervals and atomic reserve form a meaningful system.
- **V=4:** Extends existing boundary/concurrency concepts into scheduling.
- **E=2:** Public practice with original precise window and reservation rules.
- **G=5:** Small interval oracle and barriers yield objective tests.
- **F=3:** New service and fixtures with no new runtime family.

### 16. Notification feed — 76/100

Research IDs: 26; Existing.

- **D=4:** Concurrent updates and duplicate marks must converge.
- **V=4:** Distinct async state problem; some UI overlap with labels.
- **E=2:** Documented local challenge, no external employer match.
- **G=4:** Six probes establish store behavior; rendered badge remains explicit review.
- **F=5:** Existing React starter and runner; rendered verification still needs evidence.

### 17. Toy runway scheduler — 75/100

Research IDs: 19; New.

- **D=5:** Exclusion, readiness, priority, cancellation and closures interact.
- **V=4:** Adds open-ended event modeling, sharing ideas with load balancing.
- **E=3:** Official illustrative example, not confirmed live candidate question.
- **G=3:** Tests depend on extensive original policy and domain assumptions.
- **F=2:** Substantial simulator and clarification/calibration work.

### 18. Search, filters and routing — 75/100

Research IDs: 9; New.

- **D=4:** Coordinates browser URL state, filtering and API behavior.
- **V=4:** Adds routes and filter composition alongside existing ranking and persistence exercises.
- **E=3:** Anonymous firsthand full-stack question submission; detailed domain is our adaptation.
- **G=4:** Deterministic data but browser routing requires integration tests.
- **F=3:** React/Express patterns exist; new fixtures and browser coverage still needed.

### 19. Invoice transitions — 74/100

Research IDs: 23; Existing.

- **D=3:** Focused state-machine correction with API/state preservation.
- **V=4:** Dedicated explicit transition graph among the other nine.
- **E=2:** Documented local challenge, external use unknown.
- **G=5:** Full transition matrix and preserved amounts give exact objective checks.
- **F=5:** Existing starter and independent evaluation wiring.

### 20. Transactional wallet transfers — 73/100

Research IDs: 17; New.

- **D=5:** Durable idempotency, rollback and concurrent debits require transaction modeling.
- **V=4:** Adds atomic money movement beyond webhook retries and quoting.
- **E=1:** Original adaptation without a verified external question match.
- **G=4:** Exact balances are objective; failure injection and isolation tests need care.
- **F=2:** Requires transaction-capable fixtures and concurrency validation.

### 21. Crawler frontier and cooldown — 73/100

Research IDs: 36; New.

- **D=5:** Readiness, leases, stable priority and bounded retry form a complex state machine.
- **V=3:** Useful new semantics, but queue/retry overlap with webhook is substantial.
- **E=2:** Detailed public practice; lease/attempt contract is original.
- **G=4:** Fake-clock oracle is feasible; lease and delayed-head cases require careful fixtures.
- **F=3:** New queue scaffold but existing runtime and retry testing patterns.

### 22. Sum-15 card strategy — 73/100

Research IDs: 31; New.

- **D=4:** Separates move legality, baseline choice and quality evaluation.
- **V=5:** Adds seeded decision-strategy evaluation missing from the ten.
- **E=2:** Public sum-15 practice; generic firsthand card-game report does not authenticate this game.
- **G=3:** Legality is exact but quality metric and simulation fairness need calibration.
- **F=3:** New engine and seeded benchmark; familiar Python tooling.

### 23. Contained-string progression — 72/100

Research IDs: 38; New.

- **D=3:** Basic search, shortest output and all-pair scaling; limited domain modeling.
- **V=4:** Adds substring/multi-pattern search absent from the ten.
- **E=2:** Detailed public practice, no verified employer prompt.
- **G=5:** Small pairwise oracle gives exact results and tie checks.
- **F=4:** Small scaffold and generated lists; no UI or transactional infrastructure.

### 24. Workspace ticket labels — 71/100

Research IDs: 28; Existing.

- **D=4:** Workspace validation, persistence and client propagation interact.
- **V=3:** Shares persistence with order hold and isolation with document access.
- **E=2:** Documented local challenge, external use unknown.
- **G=4:** Five probes plus UI suite; rendered persisted selection needs review.
- **F=5:** Existing full-stack starter and evaluator wiring.

### 25. Per-user rate limiter — 70/100

Research IDs: 10; New.

- **D=4:** Boundary, identity and atomic concurrent updates provide useful depth.
- **V=3:** Overlaps tenant scoping and bounded delivery concepts.
- **E=3:** Firsthand rate-limiting theme; exact policy/limits are original.
- **G=4:** Fake-clock counts are objective; multi-instance behavior needs shared-store tests.
- **F=3:** Focused middleware and atomic store fixture.

### 26. Pricing extraction — 70/100

Research IDs: 30; Existing.

- **D=3:** Focused extraction while preserving cents, order and input immutability.
- **V=4:** Only explicit refactoring ticket among the other nine.
- **E=2:** Documented local challenge, no verified employer use.
- **G=4:** Golden outputs are objective; delegation direction needs source review.
- **F=5:** Existing working golden behavior and scaffold; extraction is intentionally unfinished.

### 27. Proration boundary — 69/100

Research IDs: 24; Existing.

- **D=3:** Focused temporal correction with offset and microsecond details.
- **V=3:** Unique subscription-period semantics but overlaps broader money/boundary practice.
- **E=2:** Documented local challenge, external use unknown.
- **G=5:** Seven probes and visible boundary fixtures give exact expectations.
- **F=5:** Existing Python billing scaffold and evaluator.

### 28. Friend recommendation — 67/100

Research IDs: 32; New.

- **D=4:** Graph candidates and held-out evaluation combine algorithms and metrics.
- **V=5:** Adds recommendations/quality assessment absent from the ten.
- **E=2:** Detailed public practice; exact quality metric is unavailable.
- **G=2:** Legality is clear, but meaningful recommendation quality and leakage control remain hard to calibrate.
- **F=2:** Requires defensible dataset, split, baseline and metric design.

### 29. Expense rules and trip aggregation — 66/100

Research IDs: 37; New.

- **D=4:** Numeric parsing, grouped thresholds and rule composition interact.
- **V=2:** Heavy overlap with existing money, rules and merge exercises.
- **E=2:** Detailed public practice without employer authentication.
- **G=5:** Exact cents and explicit predicates support straightforward independent oracles.
- **F=3:** Focused rules scaffold and grouping fixtures.

### 30. Test-contract diagnosis — 66/100

Research IDs: 20; New.

- **D=3:** Evidence-based correction of a disputed assertion rather than broad implementation.
- **V=3:** Adds valuable judgment, but works well embedded in other question debriefs.
- **E=3:** Firsthand test-alignment stage; the parser scenario is original.
- **G=4:** Explicit contract supports exact regressions; written reasoning needs review.
- **F=4:** Small parser/contract scaffold and deliberately faulty assertion.

### 31. Six-feature dashboard — 61/100

Research IDs: 14; New.

- **D=4:** Feature composition and stale requests require coherent frontend work.
- **V=3:** Duplicates much of existing React state/persistence and proposed search work.
- **E=2:** A six-feature report exists but its features are unknown; this particular dashboard is original.
- **G=3:** Interaction composition and acceptance scope need browser/manual calibration.
- **F=2:** Broad UI capstone with substantial fixtures and polish.

### 32. Watchlist persistence — 58/100

Research IDs: 8; New.

- **D=3:** Focused controller/service/store round-trip incident.
- **V=1:** Substantially duplicates order-hold and label persistence.
- **E=3:** Firsthand MovieDB failure theme; our HTTP and duplicate contract is original.
- **G=5:** Add-then-read and database uniqueness outcomes are objective.
- **F=3:** New app variant despite familiar server/UI patterns.

### 33. Order hold persistence — 58/100

Research IDs: 27; Existing.

- **D=2:** Primarily field propagation, legacy defaults and response persistence.
- **V=2:** Heavily overlaps the richer ticket-label propagation family.
- **E=2:** Documented local challenge, no verified employer use.
- **G=5:** Six probes cover round trip, isolation, Unicode and optional values.
- **F=5:** Existing scaffold and grading wiring; strong low-friction warm-up.

### 34. Verification expiry and reuse — 57/100

Research IDs: 16; New.

- **D=3:** Atomic consume and expiry improve a focused endpoint task.
- **V=2:** Overlaps current time boundaries and idempotency; adds token lifecycle.
- **E=1:** Original practice variant without verified external prompt.
- **G=5:** Fake clock and atomic consume checks are objective.
- **F=3:** New endpoint/token scaffold and concurrency cases.

### 35. Password policy consistency — 54/100

Research IDs: 11; New.

- **D=2:** Primarily a shared validation and boundary correction.
- **V=1:** Adds little beyond existing validation/boundary/route tasks.
- **E=3:** Firsthand password-validation theme; our Unicode/length policy is original.
- **G=5:** Exact type and boundary rules are readily testable.
- **F=4:** Small validator scaffold and two endpoint fixtures.

### 36. Team portal — 52/100

Research IDs: 7; New.

- **D=3:** Focused member search and role persistence with authorization.
- **V=1:** Strong overlap with labels, tenant isolation and other persistence tasks.
- **E=3:** Firsthand team-portal comment; specific search/roles are ours.
- **G=4:** API checks are clear but UI/error paths require integration review.
- **F=2:** New full-stack app despite small marginal coverage.

## Sensitivity: how much does the ranking depend on weights?

The same ratings are reweighted below. This tests the decision model, not the correctness of the subjective ratings. Scores and rank separation remain coarse.

**Balanced baseline** — D/V/E/G/F weights 30/25/15/20/10:

1. Staged maze (93); 2. Webhook retry (91); 3. Delivery accounting (88); 4. Tenant document access (85); 5. Two-heap load balancer (84).

**Evidence emphasis** — D/V/E/G/F weights 25/20/30/15/10:

1. Staged maze (90); 2. Delivery accounting (86); 3. Webhook retry (82); 4. Two-heap load balancer (79); 5. Tenant document access (77).

**Fast delivery** — D/V/E/G/F weights 25/20/10/20/25:

1. Webhook retry (94); 2. Tenant document access (89); 3. Staged maze (88); 4. Catalog suggestions (86); 5. Shipment CSV merge (85).

**Content without readiness** — D/V/E/G/F weights 35/30/15/20/0:

1. Staged maze (97); 2. Webhook retry (91); 3. Delivery accounting (91); 4. Two-heap load balancer (87); 5. Canvas editor (86).

## What to do with the rankings

1. **Keep all ten existing questions.** Scores determine prominence and development attention, not whether to delete a working warm-up. Webhook, tenant access and catalog optimization lead the existing library; store/UI/source review gaps still apply regardless of rank.
2. **Build maze and delivery first.** They are the strongest new families under this baseline. Then build load balancing, dependency impact and unique-character subsets as comparatively focused, deterministic additions. Public practice supports the [unique-character progression](https://algo.monster/ai-coding-interview/max-unique-characters-subset) and [dependency-impact stages](https://algo.monster/ai-coding-interview/service-dependency-impact); their company labels are not authenticated question evidence.
3. **Keep canvas on the first expansion roadmap.** Its lower grading/readiness scores reflect development cost, while its depth and distinctive frontend coverage are both 5. A useful library must cover roles, not simply take the twenty largest scalar scores.
4. **Delay compiler until its semantics and independent oracle are settled.** Its quality merits a high position, but ambiguity about liveness or division can make a difficult question unfair. This is a publication dependency, not an extra undisclosed scoring penalty.
5. **Choose at most one initial card family.** Hand comparison ranks higher for deterministic grading; sum-15 strategy fills the strategy-evaluation gap better. Use hand comparison if automated correctness is the immediate goal; use sum-15 if you can fund seeded quality evaluation and review.
6. **Retain persistence and validation tasks as warm-ups/variants.** Lower overlap scores for watchlist, team portal and password validation do not imply their real-world bugs are unimportant. They add relatively little new assessment coverage to this particular library.
7. **Review scores after mock runs.** Collect setup failure, time to reproduction, completion, wrong-fix rejection, review disagreement and outcome distribution. Update D/G/F only when evidence justifies it; do not silently change candidate scoring or historical results.

The earlier fixed 8-existing/12-new featured split was an editorial portfolio choice, not the top twenty produced by this numerical model. The raw top twenty now has 6 existing and 14 new families. Use the raw ranking for transparent prioritization, then intentionally preserve security, frontend, performance, refactoring and advanced-algorithm tracks when selecting featured content. No website order or assessment score was changed.

## Verification and source limits

Checked 36 unique families, complete coverage of IDs 1–38, ten existing registry matches, rating bounds, weighted arithmetic, sorted totals, and the separate new/existing ranks. The full matrix is also available as [JSON](/Users/shrutwik/Desktop/PromptCode/docs/ai-assisted-interview-scoring.json). Local/manual gaps and source provenance come from the prior source-backed catalogue; a current Reddit re-fetch of the load-balancer account failed, so its prior-reviewed evidence was retained without claiming fresh verification. No application test, production query or implementation was performed.
