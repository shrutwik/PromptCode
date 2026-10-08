# Proposal: an evidence-based rubric for the twenty AI-assisted SWE exercises

October 8, 2026. Status: research-informed pilot proposal, not implemented and not a validated hiring assessment. See [research and thirty-source bibliography](ai-enabled-swe-rubric-research-2026-10.md). The research supports the constructs more firmly than the proposed weights.

## Proposed dimensions

Keep the current six dimensions and stable identifiers. Broaden their descriptions and add observable anchors. Move five points from correctness to verification; leave the other weights unchanged. This emphasizes proving the solution without introducing a new scoring architecture.

| Existing identifier | Candidate-facing criterion | Current | Proposed pilot |
|---|---|---:|---:|
| A_correctness | Functional correctness | 35 | 30 |
| B_investigation | Problem framing and codebase investigation | 15 | 15 |
| C_fix_quality | Implementation quality | 15 | 15 |
| D_ai_leverage | AI judgment and oversight | 10 | 10 |
| E_verification | Verification and regression protection | 15 | 20 |
| F_communication | Explanation and ownership | 10 | 10 |
| Total | | 100 | 100 |

Why correctness remains largest: a useful solution must satisfy its contract. Why verification rises: independent testing, state preservation and plausible-wrong-fix controls provide evidence that an impressive draft actually works. Why AI remains ten points: the quality of delegation and review matters, but tool interaction should not overwhelm engineering outcomes. These are product judgments to test against local evidence, not percentages extracted from papers.

Use this profile for general SWEs working with AI. For engineers building AI products, create a separate task/profile with explicit evaluation, data, latency/cost and monitoring requirements. Do not quietly add those requirements to these twenty exercises.

## Anchors: what each rating means

Score 0–4 only when sufficient evidence exists. Zero means demonstrated failure, not missing telemetry. Three means meeting the stated task at the target level. Four requires stronger relevant evidence, not extra features. Partial completion need not automatically imply weak investigation or weak oversight.

### A — Functional correctness: 30

| Rating | Observable anchor |
|---:|---|
| 0 | Demonstrably breaks the core contract or cannot produce the required central behavior. |
| 1 | Some happy-path behavior works, but major required branches or invariants fail. |
| 2 | Most central behavior works; a material required edge case or regression remains. |
| 3 | Meets the stated acceptance behavior, including relevant edge cases and preserved behavior, supported by independent evaluation. |
| 4 | Meets the contract with additional evidence resolving a relevant subtle invariant or boundary beyond the minimum demonstration; no unrequested features needed. |

A passing suite is evidence, not mathematical proof. Reviewers must use the task's named failure severity and coverage notes. A suite failure caused by broken infrastructure is not demonstrated candidate failure. A correctness score must remain bound to the verified artifact and independent evaluation, as the current architecture requires.

### B — Problem framing and investigation: 15

| Rating | Observable anchor |
|---:|---|
| 0 | Misstates the central requirement or changes an unrelated component without locating the relevant behavior. |
| 1 | Guesses from symptoms; overlooks the main state, scope or boundary and cannot explain the chosen edit location. |
| 2 | Finds relevant code and some constraints, but misses an important dependency, assumption or root cause. |
| 3 | Establishes the contract, relevant code path/state model and cause; decomposes work into sensible steps. |
| 4 | Efficiently identifies a non-obvious interaction, resolves consequential ambiguity and uses evidence to narrow the solution without unnecessary exploration. |

A short written note can establish this evidence. Constant thinking aloud, an elaborate plan or a particular agent mode is not required.

### C — Implementation quality: 15

| Rating | Observable anchor |
|---:|---|
| 0 | Introduces a severe unsafe behavior, corrupting design or unusable integration. |
| 1 | Brittle patch, broad unrelated edits or major failure-handling/complexity problems. |
| 2 | Workable approach with material maintainability, boundary-handling or integration weaknesses. |
| 3 | Focused change fitting existing patterns; appropriate data structures, failure handling and complexity for stated requirements. |
| 4 | Clearly resolves a subtle design risk with a simple maintainable implementation and explicit tradeoffs; avoids speculative abstractions. |

Use concrete artifacts. Do not award points merely because formatting is attractive or an AI produced a large rewrite. Performance requirements must be explicit before assessment.

### D — AI judgment and oversight: 10

| Rating | Observable anchor |
|---:|---|
| 0 | Accepts clearly wrong or unsafe output without checking and cannot justify the resulting action despite available evidence. |
| 1 | Repeatedly delegates without relevant context or review; obvious errors persist. |
| 2 | Supplies useful context and inspects some output, but consequential assumptions or integration errors remain unchecked. |
| 3 | Chooses useful bounded assistance, gives relevant context, reviews consequential output and corrects or rejects errors; retains control of the work. |
| 4 | Adapts delegation strategically, independently validates a subtle AI assumption and chooses direct action or another tool when it is more effective. |

Do not require a deliberately planted model mistake: a candidate can demonstrate careful review of correct output. Do not score model brand, prompt length, agent count, plan-mode use or automatic test generation itself. Reviewing high-risk boundaries can be sufficient; manually authoring every line is not the goal.

### E — Verification and regression protection: 20

| Rating | Observable anchor |
|---:|---|
| 0 | Claims success despite observed contradictory evidence or actively weakens checks to hide failure. |
| 1 | No meaningful check beyond superficial execution, despite a functioning environment and opportunity. |
| 2 | Checks the main example but misses a material invariant, failure path or regression; expectations are weak. |
| 3 | Runs meaningful checks with justified expectations covering central behavior, a relevant edge/failure case and preservation. |
| 4 | Uses a discriminating counterexample, independent oracle, property or plausible-wrong-fix check that reveals a subtle defect; verifies the repair and relevant regressions. |

A test must be able to distinguish a credible incorrect implementation from the intended one. Coverage percentage, test count and a green model-generated suite are insufficient on their own. Reward meaningful existing tests as well as newly written tests; do not require test authorship for its own sake.

### F — Explanation and ownership: 10

| Rating | Observable anchor |
|---:|---|
| 0 | Cannot explain the central behavior or gives an account contradicted by their artifact. |
| 1 | Describes surface changes but cannot explain why the solution works or its main failure mode. |
| 2 | Understands the main implementation but struggles with an important limitation or a small relevant adaptation. |
| 3 | Accurately explains the change, evidence and limitations; can reason through a short relevant counterfactual. |
| 4 | Gives a precise causal explanation and adapts reasoning to a meaningful new constraint, including which assumptions and checks must change. |

Score technical content, not accent, charisma or verbosity. Provide equivalent written explanation options where appropriate. A changed-requirement probe must be announced and standardized if graded.

## Candidate-facing information and private tests

Before the session, show the six criteria, weights, anchor meanings, time box, permitted tools, required deliverables and which parts are graded. Explain that tests examine stated behavior and preservation, and that human review considers reasoning and ownership.

Keep private fixture inputs and expected answers server-side, but keep requirements public. A private case may vary inputs, ordering or boundaries within the contract; it must not introduce a new requirement. Candidates should have visible examples and runnable representative checks. Show semantic test families and feedback appropriate for practice without exposing the private answer key.

Current featured exercises have three baseline parts and a fourth optional changed-requirement discussion. **Keep Part 4 optional and ungraded under the existing contract.** If a future interview uses a graded defense, version and announce that protocol; give comparable candidates equivalent probes. Do not retroactively reinterpret existing sessions.

## Behavioral results and human review are different records

Report both:

1. **Independent behavioral outcome:** semantic families passed/failed, critical failures, evaluator version, artifact binding and environment status.
2. **Human rubric review:** six anchored ratings, short evidence references, applicable dimensions, review version and limitations.

Do not equate “100% tests passed” with “100% engineer score.” Also do not infer every dimension from test outcomes. Correctness evaluates the artifact; verification evaluates how the candidate established warranted confidence. Investigation evaluates their model and diagnosis; AI oversight evaluates delegation/review decisions. The same event may inform two dimensions only when the reviewer states the distinct behavior it demonstrates.

Pending review stays unscored. Missing evidence is not zero. An AI summary can locate evidence and suggest feedback; a human reviewer remains accountable for ratings. The current evidence/digest binding should remain intact.

### Formula and examples

For applicable dimensions, `score = 100 × Σ(weight × rating / 4) / Σ(applicable weights)`.

All six ratings of 3 yield 75/100; all ratings of 4 yield 100/100. These are anchor arithmetic, not empirically established hiring bands.

Example ratings `(A=3, B=3, C=3, D=2, E=4, F=2)` yield 75/100 with the proposed weights: 22.5 + 11.25 + 11.25 + 5 + 20 + 5. The profile matters: strong verification can coexist with ownership gaps. A different profile can have the same total, so show the dimensions and flags.

Do not let averaging hide a critical defect. For tenant access, unauthorized data exposure should be shown explicitly; for wallet transfers, loss of conservation or atomicity should be explicit. A hiring organization may define noncompensable requirements prospectively based on role risks. This proposal does not invent a universal automatic failing cutoff.

### Availability versus usage

Record whether AI was permitted, available, usable, required and actually used. Current availability of a response event is not enough to distinguish those states.

- If AI is optional and unused, report AI oversight as not observed, together with tool mode. Do not pretend that an adjusted total measures the same AI competence as a fully observed session.
- If AI or the runner fails, record an infrastructure condition and apply the standardized retry/time adjustment. Do not assign a weak ability rating from missing logs.
- If AI judgment is mandatory for the role, use an announced, standardized review of a supplied AI patch to obtain evidence even when the live model is unavailable.
- If a candidate intentionally skips a required assessment component, distinguish incomplete assessment from demonstrated incorrect reasoning. Use an explicit prospective policy rather than silently mapping all omissions to zero.

## Independent-test design

Organize checks into semantic families: baseline behavior, edge/boundary behavior, state preservation/failure atomicity, idempotency/concurrency, and explicit performance constraints where relevant. Every expected result must have an independent rationale.

Weight the family by its relevance and risk, then distribute that family's weight among its cases. Adding ten near-duplicate cases must not increase that concept's total importance. Select task-specific family weights before seeing candidate outcomes; do not apply a universal arbitrary split to every task.

Maintain known-correct repairs, meaningful partial repairs and plausible wrong repairs. Check that wrong repairs fail for the intended reason. Useful controls include greedy solutions where exact optimum is required, coordinate-only maze visitation, stale caches, split debit/credit transactions and shallow authorization checks. Mutation survival prompts review of the test or specification; not every syntactic mutation is a meaningful fault.

Use deterministic clocks, controlled failure injection and schedule control for concurrency. Preserve evaluator isolation and artifact binding. UI tasks need observable rendered behavior where the contract requires it; backend-only assertions cannot establish a correct rendered interaction. Instrumentation counters require independent review when the candidate can change them.

## Evidence map for all twenty exercises

These are task-specific review and test-design suggestions grounded in the existing briefs, not new hidden requirements or claims that every suggested check is already implemented. Changed-requirement prompts remain optional under current rules.

| Exercise | Underlying engineering problem | Plausible wrong solution / discriminating evidence | Ownership or transfer discussion |
|---|---|---|---|
| warehouse-route-planner | State identity and constrained shortest paths | Coordinate-only visited set loses routes requiring a revisit with new permissions; use a small independently reasoned graph and preserve the input map | Why does weighted movement require changing the search frontier and oracle? |
| webhook-delivery-retry | Retry policy, bounded concurrency and idempotent identity | Deduplicating results rather than effects loses per-job output; duplicate delivery IDs must share billing identity yet retain results | Which guarantees need receiver cooperation after commit-before-response loss? |
| courier-payment-ledger | Precise monetary accounting and durable payment state | Recomputing an earlier cutoff after payment double-charges; verify immutable totals and exact arithmetic | How do corrections after payment become adjustments rather than rewritten history? |
| tenant-document-acl | End-to-end authorization and scope isolation | Checking ownership only at one entry point or mutating on denial; reject foreign access and then verify authorized/unrelated state | How would explicit sharing, revocation and default denial change policy? |
| worker-job-dispatch | Event ordering, eligibility and queue fairness | Sorting the caller's input incorrectly or mishandling backlog; input permutation must preserve distinct-arrival order and FIFO | How do priorities introduce starvation and new tie rules? |
| catalog-suggest-latency | Ranked-result parity and reduced actual work | Cache repeats return old ranking after data changes; check invalidation, prefix limits and independently reviewed work measures | Who owns index/cache versions when products update? |
| bounded-recency-cache | Recency invariants and atomic failure behavior | Invalid resize mutates order before rejection; subsequent eviction must expose preservation | How do TTL, injected time and factory atomicity interact? |
| unique-word-selection | Exact combinatorial optimum and valid dominance | Greedy overlap selection misses optimum; compare small exhaustive enumeration and exclude useless empty words | Why may a mask representative cease to dominate when word values differ? |
| service-impact-analysis | Normalized scope and transitive graph reachability | String-prefix matching crosses path boundaries; test repeated deletion, root deletion and graph effects | How would environment-dependent edges alter the active graph? |
| canvas-document-editor | Coordinated UI state and reversible history | Undo followed by a new edit retains abandoned redo; observe committed history and rendered state | What becomes one history action for group dragging? |
| shipment-csv-merge | Event identity, replay safety and aggregation isolation | Replayed or unrelated records inflate another shipment; use reordered streams with an independent expected aggregate | What policy should handle conflicting content for one event ID? This is currently unspecified. |
| expression-cost-analysis | Liveness, aliases and resource accounting | Dead-code removal miscounts shared allocation peaks; compare live-work cost and alias-aware peak | Why do observable side effects invalidate reachability-only elimination? |
| structured-event-logger | Configuration atomicity and isolated event delivery | Filtering still invokes clock/sinks or rejected configuration leaks; use spies and preserved-policy assertions | What does successful delivery mean for asynchronous sinks and failures? |
| extensible-hand-comparison | Supplied-rule ordering and extensibility | Rank magnitudes override category dominance; check antisymmetry/transitivity and supplied rules | What must be specified before comparing partial hands? |
| room-reservation-scheduler | Interval boundaries and all-or-nothing reservation | Failed booking changes calendar; verify unchanged state and an adjacent valid slot | How should failed rescheduling restore the original reservation? |
| notification-feed-stale | Concurrent asynchronous state merging | A failed operation rolls back independent successes; control completion order and observe rendered state | How can a stale refresh avoid undoing a completed mark? |
| runway-event-scheduler | Event timing, occupancy and eligibility | Closure delays cause cancellation to be applied too late; process cancellation before selecting the delayed flight | Why is duplicating a single-runway queue insufficient for two runways? |
| movie-search-routing | End-to-end composition and API/UI agreement | Filters applied after pagination produce wrong totals; combine all filters before sorting and slicing at HTTP boundary | What consistency does a snapshot token or cursor provide across catalogue changes? |
| invoice-status-transition | Legal state graph and rejected-write preservation | Terminal-state rejection still edits another field; compare every field after rejected transition | How does a version check prevent concurrent conflicting transitions? |
| transactional-wallet-transfer | Conservation, atomicity and durable idempotency | A rolled-back receipt reserves its ID or a partial write loses money; inject failure and retry with the later committed payload | How do cumulative refund limits and refund idempotency share one transaction? |

The same six criteria apply, but the evidence differs. For example, “investigation” in the maze concerns state identity; in tenant access it concerns policy across entry points; in the feed it concerns asynchronous event ordering. A generic “good reasoning” label without this task specificity is insufficient.

## Pilot and validation plan

1. **Freeze contracts and anchors.** Map each graded baseline part to named invariants, test families and reviewer examples. Keep optional discussion separate. Choose role and seniority before grading.
2. **Build calibration packets.** Include known-correct, partial, incorrect, polished-but-wrong, terse-but-correct, optional-no-AI and infrastructure-failure examples. Bind snapshots, evaluator results and interaction evidence. Do not fabricate candidate validation data.
3. **Run standardized mock sessions.** Cover intended levels, languages and tool modes. Measure completion and reasoning opportunities per exercise; reduce scope or adjust time if sessions do not expose the intended constructs.
4. **Double-score independently.** Reviewers record ratings and evidence before reconciliation. Examine per-dimension agreement, ordinal confusion, weighted kappa or suitable ICC, confidence intervals and disagreement causes. A small pilot can improve anchors; it cannot establish hiring validity.
5. **Audit construct sensitivity.** Change irrelevant prose polish while retaining reasoning, then change actual semantics while retaining polish. Scores should be stable to the former and sensitive to the latter. Test AI summaries for evidence omissions and unsupported claims.
6. **Check weighting sensitivity.** Compare current and proposed profiles on the same packets. Investigate candidates whose ranking changes and whether verification was being double-counted. Do not select weights only to produce a desired ranking.
7. **Check fairness and tool confounds.** Standardize access, latency handling, permissions, accommodations and evidence opportunities. Compare results by level, language and tool mode with uncertainty; small subgroup samples cannot prove fairness.
8. **Establish predictive evidence.** With appropriate consent and governance, compare scores with independent subsequent work outcomes such as reviewed work quality and escaped defects. Separate training/calibration from held-out evaluation. Inter-reviewer agreement is reliability; job-performance prediction is validity.
9. **Version and publish deliberately.** Ship only after anchors, evaluator binding, candidate disclosure and missing-evidence behavior agree. Preserve historical scores. Keep unsupported public claims and hiring cutoffs disabled.

No particular sample count, kappa target or passing score is established by the reviewed literature for this product. Existing internal targets can be operational milestones, but should not be presented as scientifically validated thresholds.

## Minimal future implementation scope

A follow-up implementation would update rubric labels/anchors and versioning, add explicit tool-availability/assessment states, publish candidate-facing criteria, and support task-specific evidence notes. Test-family reweighting needs a separately reviewed evaluator version. Existing human review and artifact binding should remain the reference pattern.

Required verification would focus on weight totals, 0–4 bounds, missing/NA behavior, stale packet rejection, public/private data separation, optional-part exclusion, and a few discriminating task controls. The research request itself makes no runtime changes.
