# SOLUTION — extensible-hand-comparison

## Reference approach and limits

Identity validation and rank semantics are separate. Build a category plus tie key; compare that key under the supplied ordering. A suit tie-break is an invented rule; ignoring the kicker loses a specified one. Sorting is O(h log h), with h fixed at three. Explain how a rule object changes precedence without changing parser or identity checks.

Reviewed implementations are in backend/tests/ranked_reference_fixtures.py and remain interviewer/test-only.

## Initial incident

`engine.py` contains the faulty change `RANKS.get(card[0],1),card[-1]`. Repair the contract rather than changing expectations.

The candidate also implements compare from the complete hand key.

## Independent evidence

Eight server-owned observation probes cover this family; expected values never enter the candidate command. Two plausible wrong repairs are checked separately. Rendered frontend behavior retains explicit reviewer requirements even when the visible suite passes.

## Rubric (100)

Correct behavior and preservation: 35; model and explanation: 25; independent verification: 20; AI-output review and trade-offs: 20. This guide does not replace the platform rubric.

## Parts and reviewer evidence

Physical identity validates hands; category precedence and rank keys determine comparison.

- Part 1 (Parse valid identities): ten-rank, ace-rank, duplicate, invalid-order.
- Part 2 (Compare under supplied rules): category, kicker, suit-neutral, variant.
- Part 3 (Pressure-test the model): comparison-order-laws.

Part 3 checks this contract property: Category dominance must remain antisymmetric and transitive even when the weaker category has larger ranks. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: A larger rank can defeat a stronger category before category precedence is considered. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: Accept partial hands. Specify how incomplete categories compare with complete hands before coding; do not import five-card poker semantics or invent suit tie-breaks. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: Why does 10H require special parsing care? A: The entire rank token precedes the final suit; taking one character reads ten as one.
2. Q: Can matching ranks be distinct cards? A: Yes: physical identity includes the suit, while comparison intentionally does not use suit as a tie-break.
3. Q: What is a complete pair comparison key? A: Category precedence, pair rank and then kicker rank.
4. Q: What does a rule variant change? A: The supplied category ordering only; adding poker rules or suit precedence invents unstated behavior.
