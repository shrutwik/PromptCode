# SOLUTION — unique-word-selection

## Underlying invariant

A validator measures legality, not whether a strategy found the best answer. Character masks compress compatibility, not the exponential worst-case search space.

## Investigation and reference repair

Run the starter first, distinguish the initial defect from incomplete checkpoints, and map a test observation to its contract. Implement each checkpoint without weakening the supplied tests. Test-only reviewed source is in backend/tests/expansion_reference_fixtures.py and never goes into candidate delivery.

Initial faulty edit locations:

- engine.py: `if ms[i] is None or used&ms[i]:return False`.
- engine.py: `ms=masks(words);states={0:[]}`.

## Reference approach and limits

Validate a proposed index subset separately from finding an optimum. Represent a valid word by its character mask and reject words with internal repetitions from optimization. Extend compatible mask states with each input occurrence; for the same resulting mask keep the fewer-word selection, then lexicographically smaller indices. The empty selection handles zero-character inputs. This is exact state search, potentially exponential: at most 2^26 masks, with selection copying/comparison costs beyond the state count. Small exhaustive enumeration provides an independent oracle.

## Checkpoint evidence

1. Repair legality independently from optimality. Ask for the invariant, a counterexample and observed verification.
2. Implement exact compatible-subset search with explicit ties. Ask for the invariant, a counterexample and observed verification.
3. Compare small-input brute-force results and discuss larger-input pruning. Ask for the invariant, a counterexample and observed verification.

## Rubric (100)

| Criterion | Points |
|---|---:|
| Correct behavior and preserved contracts | 35 |
| Model and approach explained | 25 |
| Independent verification and counterexamples | 20 |
| AI-output review and communicated trade-offs | 20 |

This question-specific review guide does not replace the platform rubric or behavioral evidence. Do not infer understanding from a green suite alone.

## Wrong alternatives

A validator that demands maximum length rejects legal suboptimal answers. A longest-word-first greedy algorithm can miss two compatible shorter words. Comparing only total characters leaves deterministic ties undefined.

## Parts and reviewer evidence

Legality differs from optimality; index identity and deterministic ties are part of the objective.

- Part 1 (Validate independently): validator-legality, alphabet-contract, no-clean-words.
- Part 2 (Find an exact optimum): optimum-not-greedy, tie-by-index, occurrence-identity, empty-word-tie, all-26.
- Part 3 (Pressure-test the model): overlap-trap.

Part 3 checks this contract property: An exact optimum must beat a tempting overlapping word and omit useless empty words. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: The longest individually legal word always belongs in a maximum compatible subset. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: Give each word a value and maximize total value instead of unique character count. Show why keeping the fewest-word representative for a mask may no longer be a valid dominance rule. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: Can a suboptimal selection be legal? A: Yes; legality checks identity and repeated characters, while optimality is a separate objective.
2. Q: Why preserve fewer words for the same mask? A: Both selections have identical future compatibility and character count; fewer words wins the stated tie before lexicographic order.
3. Q: Should an empty word be selected? A: It adds no characters and loses the fewer-word tie, so it cannot improve an optimum.
4. Q: How do you verify exactness independently? A: Enumerate all index subsets for small inputs and compare the objective and both tie rules.
