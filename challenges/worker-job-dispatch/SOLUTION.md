# SOLUTION — worker-job-dispatch

## Underlying invariant

Readiness ordering and selection ordering are different: earliest completion chooses when to dispatch, lowest idle id chooses where.

## Investigation and reference repair

Run the starter first, distinguish the initial defect from incomplete checkpoints, and map a test observation to its contract. Implement each checkpoint without weakening the supplied tests. Test-only reviewed source is in backend/tests/expansion_reference_fixtures.py and never goes into candidate delivery.

Initial faulty edit locations:

- engine.py: `idle=list(range(k));busy=[];out=[];now=0`.
- contracts.py: `finish<arrival`.

## Reference approach and limits

Sort arrivals stably. Maintain a FIFO waiting queue, a heap of idle worker ids, and a heap of busy (finish, worker) pairs. At a decision time release every worker finishing at or before that time before choosing the lowest idle id. When all workers are busy advance to the next completion, retaining older queued work ahead of new arrivals. Sorting costs O(n log n); heap scheduling costs O(n log k), with k workers.

## Checkpoint evidence

1. Correct exact completion-boundary eligibility. Ask for the invariant, a counterexample and observed verification.
2. Implement idle-worker and in-flight scheduling with queued jobs. Ask for the invariant, a counterexample and observed verification.
3. Show deterministic ties and explain complexity using a slow small-input oracle. Ask for the invariant, a counterexample and observed verification.

## Rubric (100)

| Criterion | Points |
|---|---:|
| Correct behavior and preserved contracts | 35 |
| Model and approach explained | 25 |
| Independent verification and counterexamples | 20 |
| AI-output review and communicated trade-offs | 20 |

This question-specific review guide does not replace the platform rubric or behavioral evidence. Do not infer understanding from a green suite alone.

## Wrong alternatives

Releasing only one eligible worker can select a higher worker id even though worker zero is also free. Sorting waiting work by duration violates FIFO. Strict finish < now prevents back-to-back assignments.

## Parts and reviewer evidence

Arrival eligibility, FIFO waiting order and idle-worker selection are separate orderings.

- Part 1 (Repair eligibility): exact-boundary, invalid-duration, duplicate-id, empty-jobs.
- Part 2 (Schedule queued work): fifo-queue, simultaneous-release, sorted-arrivals, idle-gap.
- Part 3 (Pressure-test the model): queued-permutation.

Part 3 checks this contract property: Input permutation does not reorder distinct arrivals, and a backlog remains FIFO. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: Sorting a backlog by duration or input order is interchangeable with stable arrival/FIFO order. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: Add job priorities without preempting active work. Define fairness/starvation policy and stable ties, then identify which queue and oracle must change. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: Which work runs first after a busy period? A: The oldest queued arrival, with original input order breaking equal-arrival ties.
2. Q: Why release every eligible worker? A: The choice is over all currently idle workers; a partial release changes deterministic worker-id selection.
3. Q: How is the next decision time chosen? A: Use the next arrival when capacity is idle, or next completion when queued work is blocked, while processing all eligible events.
4. Q: What verifies output preservation? A: Each input job appears once with its assigned worker and exact start/finish; input records remain unchanged.
