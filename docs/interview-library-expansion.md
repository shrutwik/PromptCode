# Interview library: source review and implemented expansion

> This report records the initial twenty-question expansion. The subsequent [ranked top-twenty implementation](interview-top20-implementation.md) features the exact scorecard selection within a retained twenty-five-question library.

Reviewed and implemented October 7, 2026. The local website registry now contains **twenty questions**: ten improved existing tickets and ten new original, runnable Python challenges. This is a repository change, not a production deployment. Existing starter defects are preserved for candidates; reviewed reference repairs pass the suites.

## Source coverage and access limits

I reviewed the [AlgoMonster AI-coding catalogue](https://algo.monster/ai-coding-interview), its public guidance, and all thirteen currently linked available practice-question pages. Compound Word Finder is marked coming soon and has no linked practice page. This covers the requested AI-coding practice collection, not every unrelated algorithm/marketing page on the entire domain.

The public extracts show initial-stage statements, named tests, starter filenames and later-stage headings. Full later-stage statements, assertion bodies and editor source were not available in these extracts; prior access attempts reached a subscription boundary. I did not infer that reading a heading meant obtaining the hidden tests or clone the paid workspace. Every new prompt, implementation, fixture and grading case here is original. Company tags on practice pages are not treated as authenticated employer provenance.

| Available practice page reviewed | Underlying pattern inferred from its public material | Where the insight is used |
|---|---|---|
| [Maze](https://algo.monster/ai-coding-interview/maze_solver) | Rendering is distinct from search; permissions expand the state | Warehouse routing; preserving observable output in catalog/refactor questions |
| [Unique characters](https://algo.monster/ai-coding-interview/max-unique-characters-subset) | Legality, optimality and scale are separate checkpoints | Unique-word selection; distinguishing a valid result from a good strategy |
| [Sum-15 cards](https://algo.monster/ai-coding-interview/card-game-15-opt) | A physical occurrence cannot be reused just because a value matches | Card triples; shipment event and webhook delivery identity |
| [Friend recommendations](https://algo.monster/ai-coding-interview/friend-recommendation) | Validate exclusions before ranking or measuring quality | Tenant/label boundaries; independent correctness before performance/quality claims |
| [Compiler](https://algo.monster/ai-coding-interview/compiler-optimization) | An incorrect fixture loader can contaminate later judgments; dependencies/liveness matter | Expression analysis; counter integrity and independent verification |
| [Hand comparator](https://algo.monster/ai-coding-interview/card-hand-comparator) | Parse identity and ordering correctly before extending rules | Pricing rule-order regression; staged contractual extension |
| [Delivery](https://algo.monster/ai-coding-interview/delivery-cost-dashboard) | Monetary duration, cutoff payment and distinct simultaneous entities differ | Courier ledger; proration boundaries and webhook payment identity |
| [Expense rules](https://algo.monster/ai-coding-interview/expense-rule-engine) | Representation is not value; per-item and grouped policies differ | Exact monetary checks and aggregation reasoning in pricing/shipment/courier |
| [Service impact](https://algo.monster/ai-coding-interview/service-dependency-impact) | Path ancestry is not string prefix; impact direction matters | Service impact; explicit scope boundaries in tenant access |
| [Meeting scheduler](https://algo.monster/ai-coding-interview/meeting-scheduler) | A boundary helper can be right while reserve still races | Room scheduler; proration and async feed invariants |
| [LRU](https://algo.monster/ai-coding-interview/lru-cache-progressive) | A read changes recency; compound creation must be atomic | Bounded cache; caution about stale query caching and state snapshots |
| [Crawler](https://algo.monster/ai-coding-interview/crawler-frontier-queue) | Priority, eligibility and stable ties are different orderings | Worker dispatch; bounded webhook concurrency and input-order results |
| [Contained strings](https://algo.monster/ai-coding-interview/shared-substring-in-string-list) | Equal values at distinct positions are still separate occurrences; output semantics matter | Word/card/event identity; preserving existing exact response contracts |

## Additional sources reviewed

- [Canva engineering guidance](https://www.canva.dev/blog/engineering/yes-you-can-use-ai-in-our-interviews/) supports complex realistic work, reviewing generated code and ownership. It informed clarification and defend-the-change checkpoints, not an employer label for our questions.
- [HackerRank interview-design guidance](https://www.hackerrank.com/blog/how-to-interview-engineers-who-use-ai-coding-assistants/) describes diagnosis/explanation, changed requirements and approach comparison. It informed optional review twists kept separate from baseline acceptance.
- [Karat's evaluation lessons](https://karat.com/evaluate-ai-ready-engineers/) emphasize evidence of comprehension and decisions rather than correct output alone. Interviewer notes now require a counterexample and observed verification evidence; no automatic human-competency certification is inferred from a green run.
- [CoderPad's AI-tool documentation](https://coderpad.io/resources/docs/interview/pads/interview-ai-assist/) distinguishes tool modes, shared histories and interviewer configuration. Our instructions use scoped AI collaboration without imposing a universal external interview policy.
- Hello Interview's [orientation](https://www.hellointerview.com/learn/ai-coding/fundamentals/codebase-orientation), [planning](https://www.hellointerview.com/learn/ai-coding/fundamentals/planning-your-approach), and [verification](https://www.hellointerview.com/learn/ai-coding/fundamentals/verification-and-testing) pages informed the read/model/verify progression. Its company-format claims remain separate from our original contracts.

## What makes the existing ten more insightful

The change is to the question design, verification and reviewer guidance. The known candidate incidents are intentionally not repaired in their starters. Each README and website prompt now asks for reproduction, the invariant, a scoped repair, a rejected shortcut and evidence. Each interviewer solution includes a concrete wrong repair and an optional changed requirement. Discussion extensions are explicitly not additional baseline requirements.

| Existing question | Underlying problem made explicit | Added executable check |
|---|---|---|
| Invoice status | Directed legal graph and rejected-write preservation | Entire four-by-four graph instead of one patched edge |
| Order hold | Persisted aggregate state versus response echo | Hold → release → rehold → GET uses the current reason |
| Catalog suggest | Less work with identical observable ranking | Score wins over popularity; id ties and prefix limits stay exact |
| Notification feed | Async convergence must reach rendered state | Two quick UI actions leave both rows read and badge zero |
| Ticket labels | Validation, storage, serialization and hydration all matter | Save then remount with persisted checkboxes selected |
| Shipment merge | Identity differs from status; aggregation follows deduplication | Repartitioning files preserves output/total and input batches |
| Tenant access | Scope lookup and mutation, not just response redaction | Authorized edit preserves other tenant and untouched fields |
| Webhook retry | Attempt identity differs from delivery identity | Reprocessing the same delivery id posts twice but charges once |
| Pricing extraction | Equal outputs do not prove extraction direction | Code order within a rule type and exact rounded result |
| Proration | An instant has one period owner; display is separate | Full start credit at a timezone-equivalent instant |

Rendered checks strengthen evidence but do not eliminate the four declared review gaps: calibrated latency/counter integrity, rendered notification behavior, rendered label behavior, and pricing delegation source review. The pricing-output regression is not presented as proof of delegation direction.

## Ten new original codebases

Each linked README states the full contract and three checkpoints. Each repository contains engine.py, contracts.py, eight visible fixtures, runner setup and interviewer-only solution notes. Starter defects/incomplete operations are deliberate. The contracts specify ties, empty/unreachable output, invalid-input behavior, exact money and concurrency boundaries rather than leaving grading assumptions hidden.

| New question | Checkpoints / deeper invariant |
|---|---|
| [Warehouse routes](/Users/shrutwik/Desktop/PromptCode/challenges/warehouse-route-planner/README.md) | Render endpoints → shortest paths → badge/gate state and directed restrictions |
| [Courier payments](/Users/shrutwik/Desktop/PromptCode/challenges/courier-payment-ledger/README.md) | Precision → idempotent cutoff payments → distinct-driver activity |
| [Worker dispatch](/Users/shrutwik/Desktop/PromptCode/challenges/worker-job-dispatch/README.md) | Boundary helper → queued dispatch → complete eligible-worker release and deterministic ties |
| [Bounded cache](/Users/shrutwik/Desktop/PromptCode/challenges/bounded-recency-cache/README.md) | Recency → resize/zero capacity → atomic factory and failure handling |
| [Service impact](/Users/shrutwik/Desktop/PromptCode/challenges/service-impact-analysis/README.md) | Paths → deleted-subtree impact → reverse dependency closure and cycles |
| [Unique words](/Users/shrutwik/Desktop/PromptCode/challenges/unique-word-selection/README.md) | Legality → exact optimum → fewer-word/lexicographic ties and scaling explanation |
| [Expression analysis](/Users/shrutwik/Desktop/PromptCode/challenges/expression-cost-analysis/README.md) | Fixture metadata → alias-aware liveness → dead code and constant propagation |
| [Room reservations](/Users/shrutwik/Desktop/PromptCode/challenges/room-reservation-scheduler/README.md) | Half-open overlaps → earliest union gap → atomic reserve |
| [Card triples](/Users/shrutwik/Desktop/PromptCode/challenges/card-triple-strategy/README.md) | Physical multiplicity → deterministic chooser/removal → independent strategy reasoning |
| [Structured logger](/Users/shrutwik/Desktop/PromptCode/challenges/structured-event-logger/README.md) | Inclusive levels → isolated sink errors → copied records and atomic configuration |

These additions favor the existing Python runner for reproducible authoring without introducing ten new deployment dependencies. The current React/full-stack exercises receive stronger UI coverage; a canvas build remains a later frontend addition rather than being replaced by a misleading server-only exercise.

## Registration, grading and versioning

- Registry: twenty questions, version 2; original ten retained. New estimated durations/difficulties are provisional until mock-session calibration.
- Website tasks: all twenty registered; three checkpoints are inside one platform ticket, not automatic stage-unlock orchestration.
- Visible suites: 155 named test definitions across twenty codebases, including ten added checks for existing questions and eighty fixtures for the new questions. Parametrized tests can execute more cases than this definition count.
- Independent grading: 142 probes (62 existing + 80 new), with expectations retained outside candidate execution.
- Reference repairs and wrong-fix fixtures are server/test-only; every new family has a baseline and edge mutation detection case.
- Static publication gate uses the reviewed expected question count and quality contract rather than assuming ten forever.
- Python probe selection follows registry runner configuration, so the new families run in the existing Python image.
- Registry version 2 and evaluator v3 intentionally change result bindings; existing historical scores are not silently recalculated.

## Verification performed

1. **Isolated Docker QA: 129 passed.** This executes all twenty starters, their reviewed repairs, selected wrong repairs and reference visible suites, plus evaluator integrity checks. Reviewed repairs pass all 142 independent probes; starters retain observable defects, subject to the established catalog/pricing special cases. A full behavioral result does not close declared human-review gaps.
2. **Local expansion authoring QA: 40 passed.** Ten visible reference suites, ten independent-reference/starter checks and twenty wrong-repair checks. These subprocesses are authoring evidence, not signed candidate grading.
3. **Related registry/task/publication/calibration tests: 32 passed.** The twenty-question inventory and single-ticket presentation remain consistent.
4. **Website-service smoke check:** registry reports twenty and session workspace creation still works. No production deployment or live-user calibration was performed.
5. **Final consistency check:** clean diff; all local report links exist; twenty registered questions, 155 named visible tests and 142 independent probes. All twenty solution guides retain four review questions. Publication and task tests passed again after the documentation polish (10 tests).

Remaining release work: calibrated mock attempts and reviewer anchors for the new questions, the existing explicit review requirements, and production deployment through the normal release workflow. The source review did not obtain restricted AlgoMonster editor content or employer-private test suites.
