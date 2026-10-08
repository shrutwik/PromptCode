# Bounded cache

Recently read entries are evicted from a cache. Repair recency, then support resizing and atomic same-key creation.

## Contract

Capacity is an integer>=0. get returns None for a miss and promotes a hit; put updates/promotes and evicts least recent entries until within capacity. Missing reads do not change recency. resize validates first and evicts oldest entries. get_or_put(key,factory) returns a cached value or computes/stores one; for positive capacity, concurrent successful callers for one missing key execute the factory once. Factory exceptions are not cached. Capacity zero stores nothing. Factory calls may be serialized across keys; explain that trade-off. No TTL in this contract.

## Getting started

```sh
pip install -r requirements.txt
pytest -q
```

Start with README.md, contracts.py, engine.py and tests/test_engine.py. Preserve public signatures and the frozen tests. For extra experiments use a candidate-owned scratch.py. Do not change runner configuration to obtain a pass.

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: Successful reads/writes promote recency; compound creation and validation must preserve the bound.

### Part 1 — Restore recency

Reproduce read-driven eviction and distinguish a cached None from a miss.

Evidence to show:

- Successful reads promote entries; a cached None is a hit.

### Part 2 — Resize and create safely

Handle growth/shrink/zero capacity, same-key concurrent factories and exceptions without caching failures.

Evidence to show:

- Bounds survive resize and zero capacity; same-key creation is atomic and failed factories are not cached.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- A rejected resize must preserve both the capacity and recency order used by the next eviction.

### Part 4 — Changed requirement — optional discussion

Add TTL with an injected monotonic clock. Define the exact expiration boundary, whether expired reads affect recency, and how expiry interacts with atomic factories and resize.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
