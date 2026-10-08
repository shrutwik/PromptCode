# Warehouse routes

The warehouse route preview draws over its endpoints, and a robot cannot plan a legal route through badge-controlled passages. Complete the existing route library and explain the search state.

## Contract

Grid rows are nonempty and rectangular. # is blocked; S and E appear exactly once; . is open. Lowercase a–d are reusable badges and uppercase A–D are matching gates. Four moves cost one each, with U,R,D,L ties. Collect a badge on entering its tile. Optional forbidden edges are directed coordinate pairs. shortest_route returns a list of [row,column] including endpoints or None. render_route marks only internal open tiles with *, preserving S,E,walls and badge/gate tiles. Invalid grids raise ValueError before search. Never mutate input rows.

## Getting started

```sh
pip install -r requirements.txt
pytest -q
```

Start with README.md, contracts.py, engine.py and tests/test_engine.py. Preserve public signatures and the frozen tests. For extra experiments use a candidate-owned scratch.py. Do not change runner configuration to obtain a pass.

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: Search state is position plus acquired permissions; display must preserve topology.

### Part 1 — Preserve the map

Reproduce the rendering defect and distinguish route marks from endpoint, badge and gate tiles.

Evidence to show:

- Endpoints and permission tiles survive rendering; malformed grids are rejected.

### Part 2 — Route with permissions

Implement shortest legal traversal with deterministic neighbor ties, reusable badges and directed restrictions.

Evidence to show:

- Return the shortest legal route or None, with stated neighbor ties and reusable permission inventory.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- A coordinate must be revisited with a different permission inventory.

### Part 4 — Changed requirement — optional discussion

Give floor cells different movement costs. Explain why FIFO BFS no longer guarantees minimum cost and how state identity, tie rules and the independent oracle change.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
