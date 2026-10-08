# SOLUTION — expression-cost-analysis

## Underlying invariant

First verify the fixture oracle. Cost reduction is meaningful only if dependency and liveness semantics are explicit and preserved.

## Investigation and reference repair

Run the starter first, distinguish the initial defect from incomplete checkpoints, and map a test observation to its contract. Implement each checkpoint without weakening the supplied tests. Test-only reviewed source is in backend/tests/expansion_reference_fixtures.py and never goes into candidate delivery.

Initial faulty edit locations:

- engine.py: `validate_costs(costs);rows=parse(program)`.
- contracts.py: `return {'costs':{op:int(str(v)[0]) for op,v in costs.items()},'totals':[int(str(v)[0]) for v in totals],'program':program}`.

## Reference approach and limits

Parse the small straight-line language with an allowlisted AST grammar rather than evaluating source. Keep fixture totals as full integers. Model assignment aliases as references to the same storage; allocate a new temporary before freeing last-used operands to capture peak memory. Retain output res, remove unreachable instructions by backward dataflow, then propagate constants with division truncated toward zero. Operation costs and storage are separate metrics. The reference performs live-variable scans per instruction, so memory analysis can be O(I·T) for I instructions and T temporaries; do not describe the entire implementation as linear.

## Checkpoint evidence

1. Repair multi-digit metadata loading. Ask for the invariant, a counterexample and observed verification.
2. Analyze arithmetic cost and alias-aware temporary liveness. Ask for the invariant, a counterexample and observed verification.
3. Eliminate dead assignments and propagate/fold constants without changing semantics. Ask for the invariant, a counterexample and observed verification.

## Rubric (100)

| Criterion | Points |
|---|---:|
| Correct behavior and preserved contracts | 35 |
| Model and approach explained | 25 |
| Independent verification and counterexamples | 20 |
| AI-output review and communicated trade-offs | 20 |

This question-specific review guide does not replace the platform rubric or behavioral evidence. Do not infer understanding from a green suite alone.

## Wrong alternatives

Counting variables rather than storage double-counts aliases. Freeing operands before result allocation undercounts the peak. Python floor division gives the wrong result for negative non-integral quotients. Reading only the first digit of fixture totals makes correct code appear wrong.

## Parts and reviewer evidence

Fixture truth, storage identity, allocation timing and dataflow reachability are separate concerns.

- Part 1 (Trust the input model): metadata-values, invalid-ssa, division-zero.
- Part 2 (Measure live work): custom-cost, alias-liveness.
- Part 3 (Pressure-test the model): dead-branch, folded-program, division-rule, alias-dead-work.

Part 3 checks this contract property: Dead-code removal must reduce cost while preserving the alias-aware allocation peak of live work. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: Each alias owns storage, or operands may be freed before the result allocation is measured. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: Introduce an operation with an observable side effect. Explain why backward reachability from res alone no longer justifies removing that operation and what the optimizer must preserve. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: Why can aliases inflate a naive memory count? A: Several names may point to one allocation; count live storage identities rather than names.
2. Q: When is peak memory measured? A: After a result allocation and before last-use operands are released, with res retained as output.
3. Q: What makes dead-code removal safe? A: Backward reachability from res in this side-effect-free straight-line language; preserve all dependencies of reachable instructions.
4. Q: How does negative division fold? A: Compute a quotient truncated toward zero; floor division rounds the wrong way for negative fractions.
