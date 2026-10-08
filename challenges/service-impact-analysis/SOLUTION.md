# SOLUTION — service-impact-analysis

## Underlying invariant

String prefix is not path ancestry; dependency propagation follows the reverse of the depends-on relation.

## Investigation and reference repair

Run the starter first, distinguish the initial defect from incomplete checkpoints, and map a test observation to its contract. Implement each checkpoint without weakening the supplied tests. Test-only reviewed source is in backend/tests/expansion_reference_fixtures.py and never goes into candidate delivery.

Initial faulty edit locations:

- engine.py: `result={s for s,ps in paths.items()`.
- contracts.py: `return ('/'+ '/'.join(parts)).rstrip('/')`.

## Reference approach and limits

Normalize POSIX paths without collapsing the root to an empty string; reject dot and dot-dot components. Match equality or ancestor boundaries, distinguishing a file change from a deleted subtree. Build reverse dependency edges: if A depends on B, a change in B can affect A. Traverse with a visited set to terminate cycles and return deterministic sorted output. Direct matching costs O(w·c·L) for w watched paths, c changes and path comparison length L; closure costs O(V+E), plus sorting.

## Checkpoint evidence

1. Fix normalized path boundaries and root behavior. Ask for the invariant, a counterexample and observed verification.
2. Implement direct file and deleted-directory impact. Ask for the invariant, a counterexample and observed verification.
3. Propagate through dependents with cycle termination. Ask for the invariant, a counterexample and observed verification.

## Rubric (100)

| Criterion | Points |
|---|---:|
| Correct behavior and preserved contracts | 35 |
| Model and approach explained | 25 |
| Independent verification and counterexamples | 20 |
| AI-output review and communicated trade-offs | 20 |

This question-specific review guide does not replace the platform rubric or behavioral evidence. Do not infer understanding from a green suite alone.

## Wrong alternatives

A bare prefix makes /api affect /apix. Following dependencies forward answers what the changed service uses instead of who uses it. Recursive traversal without visited state loops on cycles.

## Parts and reviewer evidence

Path ancestry uses component boundaries; dependency impact propagates from dependency to dependent.

- Part 1 (Repair path semantics): prefix-boundary, root-normalized, unknown-service.
- Part 2 (Propagate impact): reverse-closure, dependency-direction, deleted-watch-descendant, ordinary-file-not-parent-delete, cycle-terminates.
- Part 3 (Pressure-test the model): normalized-delete-closure.

Part 3 checks this contract property: Repeated normalized deletion must preserve scope boundaries; deleting root affects every watched service. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: String prefix identifies ancestry and all slash/root forms are interchangeable without normalization. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: Add conditional dependencies enabled by environment. Define the active graph before traversal and show how using the union of all environments would overstate impact. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: How does /api differ from /apix? A: An ancestry match requires the slash boundary or exact equality.
2. Q: What does deletion change? A: Deleting a directory affects watched paths below it, even when no individual file change is listed.
3. Q: Which way does impact travel? A: From a changed dependency to its dependents, using reversed dependency edges.
4. Q: How do cycles affect the result? A: Each reachable service is visited once; cycles do not add infinite work or duplicate output.
