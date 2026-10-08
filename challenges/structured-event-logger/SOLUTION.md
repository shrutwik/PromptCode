# SOLUTION — structured-event-logger

## Underlying invariant

Logging success has a delivery policy. Independent sink failures and copied event snapshots keep observability from changing application state.

## Investigation and reference repair

Run the starter first, distinguish the initial defect from incomplete checkpoints, and map a test observation to its contract. Implement each checkpoint without weakening the supplied tests. Test-only reviewed source is in backend/tests/expansion_reference_fixtures.py and never goes into candidate delivery.

Initial faulty edit locations:

- engine.py: `except Exception:failures.append(index)`.
- contracts.py: `LEVELS[level]>LEVELS[threshold]`.

## Reference approach and limits

Use inclusive threshold comparison. Snapshot level and sinks together under the configuration lock, then create a timestamped record with copied context. Give each sink its own deep copy, continue after failures, and return failed sink indices. JSON formatting must encode structured data rather than stringify an ad hoc representation. Work depends on record size and sink count; repeated copying intentionally trades cost for isolation. Atomic configuration gives each log call a consistent configuration snapshot, not an ordering guarantee for concurrent external sinks.

## Checkpoint evidence

1. Repair inclusive severity filtering. Ask for the invariant, a counterexample and observed verification.
2. Implement sink isolation and explicit failure observations. Ask for the invariant, a counterexample and observed verification.
3. Support atomic reconfiguration and copied structured records. Ask for the invariant, a counterexample and observed verification.

## Rubric (100)

| Criterion | Points |
|---|---:|
| Correct behavior and preserved contracts | 35 |
| Model and approach explained | 25 |
| Independent verification and counterexamples | 20 |
| AI-output review and communicated trade-offs | 20 |

This question-specific review guide does not replace the platform rubric or behavioral evidence. Do not infer understanding from a green suite alone.

## Wrong alternatives

A strict threshold suppresses messages at exactly the configured level. Letting the first sink raise drops later deliveries. Shallow copies expose nested context to a mutating sink. Reading level and sinks separately can mix configurations.

## Parts and reviewer evidence

Threshold inclusion, sink isolation and configuration replacement each have their own failure boundary.

- Part 1 (Repair event eligibility): level-boundaries, unknown-emission, clock-record.
- Part 2 (Deliver isolated records): continue-sinks, sink-copies, original-context-copy.
- Part 3 (Pressure-test the model): config-atomic, configuration-next-call, rejected-config-clock.

Part 3 checks this contract property: Rejected configuration must preserve the prior policy; filtered events must not invoke the clock or sinks. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: A failed configuration may partially change the threshold, or suppressed events may consume the clock. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: Allow asynchronous sinks. Specify backpressure, timeout/cancellation and failure reporting before adapting emit; a rejected promise must not be mistaken for successful delivery. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: Is INFO delivered at an INFO threshold? A: Yes; threshold comparison is inclusive.
2. Q: What happens when sink zero raises? A: Record failure index zero, continue delivering independent copies to later sinks and return the failure list.
3. Q: Why deep-copy twice? A: Separate the record from caller-owned nested data and isolate each sink from another sink’s mutations.
4. Q: What does atomic configure guarantee? A: A log call sees one complete level/sink configuration; it does not make arbitrary external sink behavior atomic.
