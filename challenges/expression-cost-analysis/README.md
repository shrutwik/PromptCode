# Expression analysis

A fixture loader truncates cost metadata, making a small expression analyzer look correct. Repair loading, implement cost/liveness analysis, then remove dead work and fold constants.

## Contract

load_case reads JSON with costs for +,-,*,/ as nonnegative integers, totals=[time,memory], and program as assignment strings; ignore empty/comment-only lines. Programs assign each variable once and include res. Each right-hand side is one integer/name or one binary operation on integers/names; unary minus on an integer is allowed. Forward references to assigned variables and duplicate assignments are invalid; other names are inputs. analyze(program,costs,optimize=False) returns [time,peak_temporaries]. Arithmetic results allocate a temporary before last-used operand temporaries are freed; aliases share storage; inputs/literals need none. Keep the output res alive. With optimize=True, remove statements not contributing to res and fold/propagate constants. Integer division truncates toward zero; constant division by zero raises ValueError. Do not use eval or change the stated allocation convention.

## Getting started

```sh
pip install -r requirements.txt
pytest -q
```

Start with README.md, contracts.py, engine.py and tests/test_engine.py. Preserve public signatures and the frozen tests. For extra experiments use a candidate-owned scratch.py. Do not change runner configuration to obtain a pass.

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: Fixture truth, storage identity, allocation timing and dataflow reachability are separate concerns.

### Part 1 — Trust the input model

Repair full integer fixture metadata and validate the allowed grammar, SSA ordering and arithmetic error contract.

Evidence to show:

- Full integer metadata survives loading; invalid grammar/SSA and arithmetic cases follow the stated contract.

### Part 2 — Measure live work

Implement weighted arithmetic costs and alias-aware temporary liveness under allocation-before-release semantics.

Evidence to show:

- Costs reflect live arithmetic and aliases share storage; allocate results before freeing last-use operands.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- Dead-code removal must reduce cost while preserving the alias-aware allocation peak of live work.

### Part 4 — Changed requirement — optional discussion

Introduce an operation with an observable side effect. Explain why backward reachability from res alone no longer justifies removing that operation and what the optimizer must preserve.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
