# SOLUTION — card-triple-strategy

## Underlying invariant

Physical-card membership is a multiset/identity constraint. Prove legality before evaluating any strategy objective.

## Investigation and reference repair

Run the starter first, distinguish the initial defect from incomplete checkpoints, and map a test observation to its contract. Implement each checkpoint without weakening the supplied tests. Test-only reviewed source is in backend/tests/expansion_reference_fixtures.py and never goes into candidate delivery.

Initial faulty edit locations:

- engine.py: `len(ids)!=3 or len(set(ids))!=3`.
- engine.py: `return next((list(ids)`.

## Reference approach and limits

Validate distinct physical card ids separately from values. Enumerate triples of ids and choose the lexicographically smallest sorted legal triple whose values sum to fifteen. Remove exactly those ids from a copy of the table. Several cards may have equal values without sharing identity. The reference revalidates the table for each triple: worst-case O(m^4), not just O(m^3); indexing once would reduce repeated work. A deterministic legal chooser does not establish strategic optimality: quality claims need a separate metric and simulation.

## Checkpoint evidence

1. Repair identity and multiplicity validation. Ask for the invariant, a counterexample and observed verification.
2. Implement a deterministic legal chooser and safe removal. Ask for the invariant, a counterexample and observed verification.
3. Compare with the exhaustive oracle; explain a changed scoring objective without silently changing legality. Ask for the invariant, a counterexample and observed verification.

## Rubric (100)

| Criterion | Points |
|---|---:|
| Correct behavior and preserved contracts | 35 |
| Model and approach explained | 25 |
| Independent verification and counterexamples | 20 |
| AI-output review and communicated trade-offs | 20 |

This question-specific review guide does not replace the platform rubric or behavioral evidence. Do not infer understanding from a green suite alone.

## Wrong alternatives

Reusing one id three times satisfies an arithmetic sum but not the physical-card contract. Removing every matching value deletes unselected cards. Calling a lexicographic chooser optimal confuses a tie rule with a strategy objective.

## Defend-Your-Code (4)
1. Q: Can equal-valued cards form a triple? A: Yes when they have distinct physical ids; the sum rule uses values and reuse prevention uses ids.
2. Q: Which triple is returned when several are legal? A: The lexicographically smallest sorted id triple, as specified.
3. Q: What does removal preserve? A: All unselected physical cards and the original input table.
4. Q: What proves a better strategy? A: An explicitly defined outcome metric, independent trials and uncertainty; legality alone does not establish quality.
