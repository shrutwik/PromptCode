# Question rankings and recommended library

> Historical research/ranking snapshot before the October 7 expansion. For the implemented twenty-question library and verified coverage, see [the implementation report](interview-library-expansion.md).

**Numerical ranking update:** The [complete five-criterion scorecard](/Users/shrutwik/Desktop/PromptCode/docs/ai-assisted-interview-scorecard.md) now scores all 36 families, including every existing question, with explicit weights and per-criterion rationales. Use that document for the current calculated rankings. The holistic portfolio and build recommendations below are retained for comparison; they are not the calculated order.

Decision review: October 7, 2026. Recommendation: **retain the current ten, build twelve complementary additions, and feature a twenty-question core comprising eight existing and twelve new questions**. Keep order-hold persistence and proration as shorter warm-up exercises. Do not remove working content or relabel it as an employer question.

This document gives three distinct rankings: the best twenty research additions, the current ten relative to each other, and the proposed twenty-question featured library. A question family counts once: maze serialization, paths, portals and keys/doors should share a staged family rather than inflate the catalogue with three near-duplicates.

## Basis and limits

I checked the ten records in [the website registry](/Users/shrutwik/Desktop/PromptCode/challenges/interview-registry.json), their actual prompts in [levels.py](/Users/shrutwik/Desktop/PromptCode/backend/app/services/interview/levels.py), the [challenge index](/Users/shrutwik/Desktop/PromptCode/challenges/README.md), and the [research/test catalogue](/Users/shrutwik/Desktop/PromptCode/docs/ai-assisted-interview-catalogue.json). The registered ten match the ten previously researched. All currently have one ticket/level, all are labeled medium, and their registered durations span 28–35 minutes. This is a repository-backed comparison, not verification of a deployed production database or current user outcomes.

Ranks are editorial product judgments, not measured hiring frequency, psychometric validity or completion rates. I weighed:

1. Engineering depth with AI available: does the task require comprehension, verification and a defensible decision beyond generation?
2. Additional coverage relative to the ten: does it add a genuinely different skill or merely rename an existing bug?
3. Research support: official guidance, a firsthand account, a public practice specification, or an original adaptation. These are not interchangeable.
4. Fairness and grading: clear contracts, independent oracles, reproducible failures and practical review requirements.
5. Delivery effort: reuse of existing Python/Node/React patterns and the burden of new fixtures, grading and calibration.

Existing implementation improves readiness, not interview depth. Strong employer-name recognition cannot compensate for vague or unfair grading. No numeric score is given because there are no calibrated measurements that justify a precise score.

Canva's [official account](https://www.canva.dev/blog/engineering/yes-you-can-use-ai-in-our-interviews/) supports evaluating code comprehension, ambiguity, debugging and ownership. It does not establish that each proposed exercise is a Canva interview question. Public practice stages such as [maze](https://algo.monster/ai-coding-interview/maze_solver), [delivery](https://algo.monster/ai-coding-interview/delivery-cost-dashboard), and [compiler](https://algo.monster/ai-coding-interview/compiler-optimization) inform exercise design but do not authenticate employer attributions.

## Best twenty research additions

Effort is relative: M means a focused new scaffold and independent grader; L adds substantial UI, concurrency, simulation or language-analysis work. These are scope estimates, not delivery-time commitments. Existing scaffold reuse can reduce them.

| New rank | Question family | Research exercise IDs | Evidence | Overlap with current ten | Why this position / decision | Effort |
|---:|---|---|---|---|---|---|
| 1 | Staged maze: codec/rendering → shortest path → directional edges → keys/doors | 1–3 | Firsthand maze account plus public practice; precise contracts are ours | Low | Best missing progressive algorithm family; one codebase supports escalating diagnosis and state modeling. Build first. | M |
| 2 | Delivery costs, cutoff payments and peak active drivers | 12 | Firsthand theme plus detailed public practice | Some money/boundary overlap | Adds a coherent evolving object model, idempotency and temporal aggregation beyond an isolated money bug. Build first. | M |
| 3 | Search, combined filters and direct browser routes | 9 | Anonymous full-stack interview submission; our dataset/rules | Moderate with catalog and labels | Adds browser/API integration and routing; catalog ranking optimization does not cover URL state or deep links. Build first. | M |
| 4 | Small canvas editor with document state | 6 | Firsthand frontend account; persistence/undo extensions are ours | Low | Strongest missing open-ended frontend build; visible usable output and many explainable design choices. Build a bounded MVP. | L |
| 5 | Progressive LRU cache with resize and atomic creation | 15 | Public practice; TTL is an independent original extension | Low/moderate with retry/concurrency | Clean deterministic tests, data structures and concurrency. Start with recency/resize; make TTL a separate variant. | M |
| 6 | Earliest-slot meeting scheduler with atomic reservations | 35 | Public practice; precise reserve/window rules are ours | Some boundary/concurrency overlap | Integrates interval reasoning, ordered data and race prevention into a distinct system. | M |
| 7 | Transactional wallet transfers under retries | 17 | Original practice adaptation; no verified employer attribution | Moderate with webhook and money exercises | Adds durable all-or-nothing transactions and conflicting idempotency payloads; do not count it as just another retry bug. | L |
| 8 | Service dependency impact from changed/deleted paths | 34 | Public practice | Low | Adds graph propagation, path semantics and cycle handling; unusually complementary to the current product tickets. | M |
| 9 | Deterministic two-heap load balancer | 4 | Firsthand AI-permitted account; dispatch contract is ours | Low | Useful algorithm/event-ordering family, but a bare textbook two-heap implementation is easy to outsource. Add explicit queues and a changed constraint. | M |
| 10 | Straight-line compiler cost, dead code and constants | 33 | Public practice | Low | Excellent advanced comprehension and analysis; delayed because memory semantics and oracle correctness require careful authoring. | L |
| 11 | Configurable logger with sink failure isolation | 5 | Anonymous reported logger theme; employer attribution disputed | Low | Adds library/API design and failure policy; needs meaningful stages to avoid becoming boilerplate generation. | M |
| 12 | Sum-15 card validation and strategy evaluation | 31 | Public practice; a separate firsthand account names a generic card game | Low | Adds legality-versus-quality and seeded simulations, which the ten lack. Hard legality must be graded independently from strategy quality. | M |
| 13 | Maximum unique-character subset | 18 | Public practice; weaker community employer attribution | Low | Good validation and search exercise, but less engineering breadth than the first twelve. Add larger inputs and an independent oracle. | M |
| 14 | Crawler frontier with priority, readiness and cooldown | 36 | Public practice | High/moderate with webhook queue/retry | Valuable delayed-work semantics, but overlaps an existing strong challenge. Add after demonstrating demand for queue internals. | M |
| 15 | Per-user rate limiter | 10 | Firsthand rate-limiting theme; exact limiter policy is ours | Moderate with tenants and bounded delivery | Relevant and gradeable, but a basic fixed-window fix is narrow. Use atomic updates and multi-instance follow-up to differentiate it. | M |
| 16 | Numeric expense rules and per-trip aggregation | 37 | Public practice | High with pricing, proration and merge | Adds grouping/composite rules, but expands an already represented money/rules area. Make explanation of violations part of the output. | M |
| 17 | Friend recommendation and held-out evaluation | 32 | Public practice | Low | New graph/quality domain, but recommendation quality is easy to grade misleadingly. Define withheld data and a baseline before publication. | L |
| 18 | Watchlist persistence repair | 8 | Firsthand MovieDB account | High with order hold and ticket labels | Strong reported theme but low marginal coverage: another write/read persistence bug. Prefer a themed variant or part of the search app. | M |
| 19 | Extensible hand comparison | 13 | Firsthand generic card-game theme plus public hand-comparator practice | Some overlap with new sum-15 family | Solid parser/comparison/rule-extension work; delay the second card family until the first earns its place. Do not conflate their games. | M |
| 20 | Six-feature dashboard | 14 | Firsthand six-feature repo theme; the actual six features are unknown | High with existing React/store/labels and proposed search | Broad but costly and redundant initially. Use as a later capstone after focused frontend exercises, rather than a first addition. | L |

Detailed prompts and eight original fixture scenarios for each research exercise are in the [deep dive](/Users/shrutwik/Desktop/PromptCode/docs/ai-assisted-interview-deep-dive.md). Maze IDs 1–3 contribute 24 scenarios to the combined family; the other selected nineteen contribute 152, for **176 original scenarios** relevant to this shortlist. They are test designs, not recovered hidden tests or executable completed suites.

Evidence behind reported themes: [Meta maze account](https://www.reddit.com/r/leetcode/comments/1p35b98/meta_e4_software_product_interview_experience/), [Microsoft load-balancer account](https://www.reddit.com/r/leetcode/comments/1sfgtu3/ai_assisted_coding_interview_experience_microsoft/), [Amazon search/routing submission](https://www.glassdoor.com/Interview/You-are-given-a-full-web-application-codebase-frontend-and-backend-Identify-and-fix-bugs-including-broken-search-filter-QTN_8998301.htm), [Canva frontend notes](https://www.reddit.com/r/cscareerquestionsOCE/comments/1t1jfxx/canva_interview_notes/), [Rippling theme report](https://leetcode.com/discuss/post/7649290/), [MovieDB report](https://www.reddit.com/r/amazonemployees/comments/1vhkpas/amazon_backend_oa_questions_2026_greedy_coding/), [logger discussion](https://www.reddit.com/r/leetcode/comments/1wpb4da/atlassian_ai_enabled_interview/), and [six-feature discussion](https://www.reddit.com/r/Frontend/comments/1rk9d65/frontend_interviews_in_the_age_of_ai/). Reported names and anonymous accounts remain unverified; each detailed proposed contract is ours.

## Rank and disposition of the current ten

These ranks evaluate contribution to a broad practice library, not severity of the production incident. A financially important boundary bug can still be a narrow standalone assessment. Visible definition counts are not executed assertion counts; trusted probes can cover whole matrices.

| Existing rank | Current website title / slug | Visible definitions / trusted cases | Recommendation | Concrete improvement |
|---:|---|---|---|---|
| 1 | Webhook retry / webhook-delivery-retry | 5 / 6 | Keep featured | Make per-delivery charge policy and batch result order explicit. Add a follow-up contrasting in-process deduplication with durable idempotency; preserve the existing retry/concurrency baseline. |
| 2 | Document access / tenant-document-acl | 7 / 9 | Keep featured | Preserve bidirectional GET/PATCH isolation, response non-disclosure and rejected-write checks. An optional second resource can test whether the candidate generalized the policy. |
| 3 | Search suggest / catalog-suggest-latency | 7 / 5 | Keep featured; strengthen review evidence | Preserve exact rank parity. Require calibrated performance evidence and review scan-counter integrity; the trusted five probes do not establish the 200ms requirement. |
| 4 | Notification feed / notification-feed-stale | 5 / 6 | Keep featured; strengthen rendered verification | Add a deterministic rendered-badge interaction check to complement store probes. Keep duplicate concurrent marks and rejected-call state preservation. |
| 5 | Ticket labels / workspace-label-propagation | 7 / 5 | Keep featured; strengthen rendered verification | Verify selection after save/reload in the real component. Protect mixed foreign-label rejection and unchanged previous selections. |
| 6 | Shipment CSV / shipment-csv-merge | 6 / 6 | Keep featured | State timestamp/tie and duplicate-conflict rules clearly; test any newly specified conflict rule independently. Retain snapshot reset, negative quantities and distinct same-status events. |
| 7 | Invoice status / invoice-status-transition | 8 / 6 | Keep featured as an entry point | Retain full transition matrix and rejected-state preservation. Add a changed business rule only in a versioned follow-up, without silently changing the baseline graph. |
| 8 | Pricing rules / pricing-rule-extract | 7 / 6 | Keep featured; strengthen source review | Output parity already holds in the starter. Verify that quote calls extracted applyRules, rather than applyRules calling quote; test success cannot prove extraction direction. |
| 9 | Period boundary / subscription-proration-boundary | 7 / 7 | Keep as warm-up / money-track prerequisite | Keep exact offset/microsecond cases. It is relatively narrow even with strong boundaries; move temporal aggregation depth into delivery rather than inflate this ticket. |
| 10 | Order hold / order-hold-reason | 6 / 6 | Keep as onboarding / persistence warm-up | Keep legacy nulls, Unicode overwrite and round-trip verification. De-emphasize in the featured core because labels and watchlist already cover deeper versions of field propagation. |

There are **65 visible named definitions and 62 trusted probes** across the ten. The four explicit additional review families are catalog performance/counter integrity, notification rendering, ticket-label rendering and pricing delegation. The [exact source appendix](/Users/shrutwik/Desktop/PromptCode/docs/ai-assisted-interview-local-tests.md) preserves all fixtures and observations. Counts alone do not establish fairness, difficulty or readiness to publish.

## Proposed featured twenty, ranked overall

This is the recommended presentation portfolio, not the build order. New questions are not currently implemented or release-ready. Existing questions are available in the repository, not newly certified by this review.

| Overall rank | Question | Status | Distinct value |
|---:|---|---|---|
| 1 | Staged maze | New | Progressive graph modeling and stateful search |
| 2 | Delivery accounting | New | Evolving domain model, time and idempotent payments |
| 3 | Webhook retry | Existing | Retry effects, attempt bounds and concurrency |
| 4 | Document access | Existing | Authorization and state non-disclosure |
| 5 | Search/filter/routing | New | End-to-end browser/API behavior |
| 6 | Canvas editor | New | Open-ended frontend delivery and document state |
| 7 | Progressive LRU | New | Data structures, invariants and atomic creation |
| 8 | Meeting scheduler | New | Intervals and atomic reservation |
| 9 | Search suggest | Existing | Performance under output invariants |
| 10 | Notification feed | Existing | Async state convergence and rendered consistency |
| 11 | Wallet transfers | New | Durable transactions and retry conflicts |
| 12 | Dependency impact | New | Path boundaries and graph closure |
| 13 | Load balancer | New | Event ordering and heap scheduling |
| 14 | Ticket labels | Existing | Cross-stack persistence and workspace validation |
| 15 | Compiler analysis | New | Dependencies, liveness and semantics-preserving optimization |
| 16 | Configurable logger | New | API design, configuration and failure isolation |
| 17 | Sum-15 strategy | New | Legal decisions and reproducible strategy evaluation |
| 18 | Shipment merge | Existing | Identity, deduplication and ordered ingestion |
| 19 | Invoice status | Existing | State-machine invariants |
| 20 | Pricing extraction | Existing | Refactoring without changing observable behavior |

## What to do next

**First improve measurement on the current ten.** Address the four explicit review gaps before advertising fully automated correctness. Record time-to-first-reproduction, completion, observed wrong repairs, review disagreement and setup failures. Reassess difficulty labels using mock sessions and the existing calibration workflow, rather than assuming every ticket is medium because the registry says so. These recommendations do not assert that the repository lacks every review mechanism; they identify evidence needed for each question's claim.

**Build in four batches of three:**

1. Maze, delivery accounting, search/filter/routing. These fill large gaps with relatively reusable scaffolds and comparatively concrete research themes.
2. Canvas editor, progressive LRU, meeting scheduler. Add frontend build depth and deterministic stateful systems. Keep canvas scope small enough to complete a useful baseline.
3. Wallet transfers, dependency impact, load balancer. Add transactions and stronger algorithmic variation after the basic publication path works for new questions.
4. Compiler analysis, logger, sum-15 strategy. These require especially deliberate semantics, design criteria or quality metrics; avoid rushing their graders.

For a staged maze, support independent starting snapshots or intentional stage progression with immutable grading cases. The current one-level ticket format must be reviewed before promising automatic multi-stage unlocks. A safe first release can expose one coherent baseline ticket plus explicit follow-ups without requiring new orchestration. Do not make serializer, BFS and keys/doors three featured slots by default.

**Use the existing publishing workflow.** For each addition, provide a bootable candidate scaffold, README, independent visible tests, interviewer-only solution/rubric, trusted behavioral inventory, explicit remaining review requirements, runner/registry/task wiring and reviewed reference repairs. Show that a correct repair passes and a plausible wrong repair fails; check candidate material does not expose grading outputs. Follow [the challenge revision workflow](/Users/shrutwik/Desktop/PromptCode/docs/challenge-revision-workflow.md) for versioning and historical sessions. Calibrate before selecting advertised difficulty and duration; do not copy our proposed 45–90 minute practice budgets into the registry without evidence.

**Keep the eight other shortlisted additions in backlog.** Revisit unique subsets, crawler, limiter, expense rules, recommendations, watchlist, hand comparison and dashboard after the twelve. Use watchlist as an alternative MovieDB starter or a search-app follow-up; do not add a second nearly identical persistence exercise merely to increase the count. Password validation, verification expiry, team portal and contained strings are better warm-ups or extensions initially. The runway example is useful for open-ended modeling but its aviation domain adds complexity without filling the largest current gaps. Test-contract diagnosis should be part of selected question debriefs rather than require a standalone featured slot.

**Do not use company labels as promises.** Label publisher-only or original exercises by skill/theme, with research references on an explanatory page. Neither an anonymous report nor a commercial company tag supports claiming the exact current employer question or its private tests.

## Review checkpoint

- Compared ten registry entries with ten task definitions and the research catalogue; confirmed counts and single-level format.
- Selected twenty unique research families; merged maze IDs 1–3, preserving the source exercise mappings.
- Proposed twenty featured questions: eight existing plus the first twelve research additions.
- Retained the other two existing questions as warm-ups; no deletion, website edits or scoring changes were performed.
- This is a research/product-prioritization document. No candidate application tests, production database check, implementation or release certification was performed.
