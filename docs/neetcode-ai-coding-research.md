# NeetCode AI coding research

Reviewed October 8, 2026. Research only: no challenge, ranking, grader or website behavior changed.

## Coverage and access

The [live collection](https://neetcode.io/practice/ai-coding) displayed **six questions**, with aggregate difficulty counts of two Medium and four Hard. Its initial text extraction omitted the question rows; the rendered browser confirmed all six. Individual difficulty labels were not reliably exposed, so none are assigned here.

NeetCode describes three stages—Bug Fix, Implementation, Optimization—with passing tests and an explanation before advancement. It offers written reflection and a mock mode with voice follow-up and evaluation. These are product descriptions, not independently validated assessment outcomes.

Read all six public solution pages, including their expanded three-phase explanations and available Python reference code, and the initially loaded public discussions. Language controls also advertise Java, C++ and TypeScript; those implementations were not audited. Starting a question displayed a sign-in requirement. Consequently, the full session statements, starter repositories, runnable test suites, hidden assertions, exact scoring rules and voice evaluation were **not obtained or executed**. Discussion counts are not evidence that every paginated comment was read.

Each section below separates public findings from **original proposed fixtures**. The fixtures are not NeetCode tests and have not been implemented. Performance sizes and budgets mentioned by the solutions are author claims, not measured results from this research. These practice questions are not verified employer interview questions.

## Six-question inventory

### Triplet Draw

[Public solution](https://neetcode.io/ai-coding/solution/triplet-draw).

Observed: `src/card.py` repairs rank-and-suit identity; `src/hand.py` repairs configurable ace and face-card values. `src/game.py` finds target-sum triples of distinct increasing indices, with request validation and ordered output. The implementation enumerates triples; optimization groups indices by value and looks up complements. The explanation references a 1,500-card sparse case and six-second budget. Public comments report earlier cubic implementations passing; this does not establish current behavior.

Insight: preserving occurrence identity is more subtle than ordinary value-based three-sum. For the shown binary-search approach, describe cost as O(n² log n + K), where K is output size; dense answers can themselves be cubic.

Original proposed fixtures:

| Input/action | Expected observation |
|---|---|
| Same rank, different suits | Unequal cards |
| Equal card objects | Equal hashes; collisions need not imply equality |
| Ace under both policies; all face ranks | Policy-specific ace; faces score 10 |
| Values `[3,3,3,3]`, target 9 | Four increasing index triples |
| Too-small target or hand | Reject before search |
| Large sparse versus dense hands | Measure work separately from output emission |

### Word Reveal

[Public solution](https://neetcode.io/ai-coding/solution/word-reveal).

Observed: `src/validator.py` and `src/reveal_state.py` repair case handling and completion. The turn loop validates, normalizes, ignores repeat guesses, records history, reveals matches and counts misses. Optimization indexes letter positions, maintains revealed count and caches displayed state. Explanations reference a 20,000-letter secret and 5,000 repeated guesses on a 50,000-letter secret. Discussions question reflection timing and report language-specific judge failures; these are unverified reports.

Insight: speeding up matching alone misses repeated rendering costs. The reference uses ASCII ranges while its explanation suggests `isalpha()`; those accept different alphabets. Specify the domain before testing.

Original proposed fixtures:

| Input/action | Expected observation |
|---|---|
| Secret `BaB`, guess `b` | Reveal both matching positions |
| Repeat same guess with different case | No new history entry or miss |
| Empty/multiple-character/non-string guess | No state change |
| Wrong fresh guess | Exactly one miss |
| Reveal last missing letter | Completion changes once |
| Repeated display, then a new hit | Reuse display until a real state change |

### Delivery Grid

[Public solution](https://neetcode.io/ai-coding/solution/delivery-grid).

Observed: `src/grid.py` fixes bounds, destination-cell costs and stale teleport coordinates. Routing visits all pickups and finishes at a depot. The first approach enumerates pickup orders and runs Dijkstra per leg; optimization caches key-node distances, applies subset DP and reconstructs the grid path. Explanations mention `test_solver.py`, about five pickups, a 50×50 grid and five-second budget. Discussions raise a possible conflict about globally single-use teleporting; the public solution treats teleporting as a zero-cost edge. The session contract was unavailable, so that conflict remains unresolved.

Insight: an optimal scalar cost is insufficient if the returned route skips required stops or violates resource rules. Shared history can invalidate pairwise-distance decomposition.

Original proposed fixtures:

| Input/action | Expected observation |
|---|---|
| One-row grid at its edge | No out-of-range neighbor |
| Short expensive path versus longer cheap path | Minimum cost, not fewest steps |
| Overwrite a teleport endpoint | Cached pair invalidated |
| Disconnected required pickup | Explicit impossible result |
| Route crossing another pickup early | All required pickups accounted for |
| Single-use teleport variant | Track consumption across the entire route |

### Streaming Analytics

[Public solution](https://neetcode.io/ai-coding/solution/streaming-analytics).

Observed: `src/window.py` fixes inclusive cutoff retention and stale extrema after eviction. `src/pipeline.py` processes named windows, metric rules and cooldown-based alerts, then returns aggregate summaries. Optimization uses monotonic deques for amortized constant-time extrema maintenance. The explanation references 10,000 events and a three-second budget. Discussions report missing optimization pressure and mismatched reflection prompts; these are historical user reports.

Insight: window semantics, aggregate correctness and alert state are separate contracts. A rule object carries cooldown state, so sharing it across windows creates a policy question. Ordered timestamps are also an assumption worth making explicit.

Original proposed fixtures:

| Input/action | Expected observation |
|---|---|
| Window 4; events at 2 and 6 | Earlier event retained at exact cutoff |
| Advance beyond cutoff with a former extreme | Min/max reflect surviving values |
| Equal extrema at different timestamps | Expiring one preserves the other |
| Cooldown just below and at threshold | Suppression then eligibility |
| Two windows triggering one rule | Follow explicitly declared cooldown scope |
| Generated ordered stream | Every aggregate agrees with a simple scan oracle |

### Build System

[Public solution](https://neetcode.io/ai-coding/solution/build-system).

Observed: `src/graph.py` repairs reverse edges and prerequisite counts. The next phase assigns dependency-ordered tasks to workers and calculates a critical path. Optimization uses worker heaps and downstream critical-path priorities. The explanation references 200 tasks/eight workers and a branching workload. It acknowledges that its scheduling heuristic does not guarantee the global minimum makespan. Discussions focus on how much code AI should write.

Insight: transitive impact, unlimited-worker critical path and bounded-worker scheduling are different outputs. Feasible schedules require correct dependency direction, exclusive worker occupancy and all prerequisites completed before start. Do not turn small fixture optima into a universal optimality claim.

Original proposed fixtures:

| Input/action | Expected observation |
|---|---|
| Chain with durations 2, 5, 1 | Critical-path duration 8 |
| Diamond dependency | Join starts after both parents finish |
| Cycle | Explicit failure, no partial success |
| Simultaneous completions | Release all eligible workers |
| Long chain plus independent short work | Measure priority effect on makespan |
| Tiny DAGs with exhaustive oracle | Compare heuristic quality without asserting universal optimality |

### Word Bag Maximizer

[Public solution](https://neetcode.io/ai-coding/solution/word-bag-max).

Observed: `src/char_set.py` repairs duplicate-letter validity and ignores nonletters after lowercasing; `src/word_bag.py` scores distinct letters rather than word count. Subset search filters unusable words, backtracks and caches results. Optimization uses alphabet masks and branch-and-bound. The explanation references a 30-word stress case and 26 surviving singleton letters. Public discussion warns that blindly forwarding requirements can pass toy exercises.

Insight: normalization changes what constitutes a duplicate. A pruning bound must never underestimate attainable score; sort changes must preserve original occurrence identity if returned selections need it. Cached results require a stable input contract.

Original proposed fixtures:

| Input/action | Expected observation |
|---|---|
| `Aa` | Duplicate after normalization; invalid |
| `a-1b` | Two relevant letters under NeetCode's policy |
| `[abcd, abe, cdf]` | Choose latter pair; score 6 |
| Empty and punctuation-only words | No score contribution |
| Query score and chosen words repeatedly | Same answer; avoid redundant search |
| Generated small word lists | Optimized score equals exhaustive subset oracle |

## What this changes for our current twenty

The following ordering ranks **additional value to our existing library**, not NeetCode difficulty, employer frequency or a revision of our earlier scorecard. Criteria are missing skill coverage, underlying depth, independent grading feasibility, overlap and implementation cost. Current contracts were compared with the local challenge READMEs and [latest refinement](interview-top20-refinement.md).

| Priority | Family | Existing overlap | Recommendation |
|---:|---|---|---|
| 1 | Streaming Analytics | Temporal behavior exists, but no complete streaming-window/alert exercise | Best new original question to prototype |
| 2 | Build System | `service-impact-analysis` and `worker-job-dispatch` | Advanced extension combining graph readiness and worker scheduling; preserve the existing FIFO task |
| 3 | Delivery Grid | `warehouse-route-planner`, featured #1 | Develop its weighted-routing discussion into a separately contracted advanced variant |
| 4 | Word Bag Maximizer | `unique-word-selection`, featured #8 | Strengthen performance evidence and pruning explanations; avoid duplicating the question |
| 5 | Triplet Draw | `card-triple-strategy`, additional practice; partial domain overlap with featured hand comparison | Improve index identity, output-sensitive complexity and negative controls in the additional exercise |
| 6 | Word Reveal | No exact equivalent; state-machine overlap with invoices/editor | Useful easier onboarding exercise, lower priority for the flagship twenty |

These priorities do not justify removing a featured question immediately. Streaming analytics warrants a prototype and candidate calibration before changing the selection. Dependency scheduling warrants a separate extension because critical-path priority would conflict with our worker dispatch's current FIFO contract. Keep security, concurrency, transactions and UI behavior represented; NeetCode's six mostly emphasize algorithmic model repair and optimization.

Our word-selection contract explicitly requires lowercase a–z and rejects nonalphabetic input. NeetCode's normalization policy must **not** be copied into it silently. Similarly, our maze currently discusses weighted movement as an optional change; teleporting and pickup ordering would be new requirements, not missing baseline fixes.

## How to make the exercises more insightful

1. **Ask for a prediction before running AI-written code.** Have the candidate predict one deliberately awkward fixture, name the violated invariant and point to the state that controls it. Grade the subsequent explanation with observable anchors, not length or confidence.
2. **Match reflection to the work.** Diagnosis: explain cause and smallest repair. Implementation: describe model and rejected alternative. Optimization: provide before/after work counts, preserved semantics and memory cost. Changed requirement: explain what assumption breaks. Show these prompts before the task begins.
3. **Separate behavioral success from demonstrated understanding.** An independent test pass establishes observed behavior. A reviewer should also ask the candidate to trace an unfamiliar input and review one plausible AI error. Avoid claiming comprehension from automatic test success alone.
4. **Measure meaningful optimization.** Check result parity against a small independent oracle. Use workload families that expose the intended bottleneck and known slow controls. Prefer operation counts where practical; if time limits are used, calibrate them per supported runtime. Distinguish output size from avoidable work.
5. **State the AI policy plainly.** Say whether generated code, explanations, repository edits and external tools are permitted. Evaluate whether the candidate can review and defend the result. Do not infer ability from how many lines were typed manually.
6. **Test the evaluator as a product.** Include malformed result output, ordinary diagnostic logs, crashes and unavailable infrastructure. Distinguish execution failure from incorrect candidate behavior. Test empty reflections if they affect scoring. Public comments are prompts for these checks, not proof our own grader has those defects.
7. **Keep extensions honest.** State ordering, normalization, cache invalidation, cooldown scope, reusable versus consumable resources and scheduling objectives. A heuristic needs a feasibility contract and quality measurements; exact optimum requirements need an exact oracle or appropriately bounded domain.

Our current twenty already have four explicit parts, independent fixtures and reviewer guidance. They remain one ticket: **no gated advancement, voice debrief or automatic explanation score** is implemented. NeetCode's progression is a product design worth evaluating separately, rather than presenting our existing parts as equivalent functionality.

## Suggested next implementation batch

- Author an original streaming monitoring repository: event model, time-window aggregates, alert policy and pipeline. Start with ordered timestamps and an injected clock; defer late-event/watermark semantics to a documented variant. Pair simple reference scans with boundary and duplicate-extreme fixtures.
- Prototype dependency-aware build scheduling separately: graph model, readiness queue, worker timeline and critical-path report. Require feasibility and deterministic ties; make priority improvement measurable without promising a globally optimal schedule.
- Turn weighted maze routing into an advanced variant only after defining costs, permission-state identity, route validity and ties. If teleporting is introduced, decide whether its use is reusable or globally limited before choosing a distance-cache design.
- Improve existing word/card exercises with oracle parity and slow incorrect controls after checking what their current suites already cover. Do not add duplicate tests simply because this report lists a similar idea.

## Verification and remaining gaps

Confirmed the rendered six-row inventory, opened all six corresponding solution URLs, expanded both later phases on each, and reviewed the public explanatory content. Confirmed the sign-in boundary by attempting to open Triplet Draw. Compared the relevant local contracts and latest twenty-question refinement. This report contains **36 proposed fixture ideas**, not a recovered NeetCode suite.

Still unavailable: full session requirements, all exact tests/assertions, company-tag provenance, alternate-language correctness, complete paginated discussions and measured judge behavior. No claim of exhaustive correctness or current defect reproduction is made. Before implementation, promote each proposal to an explicit contract, independently expected fixture and calibrated evaluation requirement.
