# Hand comparison

Cards are strings with rank 2..10,J,Q,K,A and suit C,D,H,S. parse_card returns (numeric_rank,suit). A hand has exactly three distinct physical cards; equal ranks in different suits are permitted. Default categories, weakest first, are distinct, pair, triple. Keys are ranks descending for distinct, (pair rank,kicker) for pair, and (rank,) for triple. compare returns -1,0,1 and never uses suits as a tie-break. An optional order must be a permutation of those three category names; it changes category precedence only. No straights, flushes or partial hands. Invalid cards, hands or orders raise ValueError without mutating inputs.

## Verification

Run `pytest -q`. Start with the listed entry files and tests; starters intentionally contain a defect. A passing suite is evidence, not a substitute for explaining the invariant.

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: Physical identity validates hands; category precedence and rank keys determine comparison.

### Part 1 — Parse valid identities

Repair multi-character ranks and reject invalid or repeated physical cards.

Evidence to show:

- Parse the entire rank token; reject repeated physical cards and invalid rule orders.

### Part 2 — Compare under supplied rules

Implement complete category/tie keys, neutral suits and an explicit category-order permutation.

Evidence to show:

- Category, pair kicker and descending rank keys determine -1/0/1; suits do not break ties.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- Category dominance must remain antisymmetric and transitive even when the weaker category has larger ranks.

### Part 4 — Changed requirement — optional discussion

Accept partial hands. Specify how incomplete categories compare with complete hands before coding; do not import five-card poker semantics or invent suit tie-breaks.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
