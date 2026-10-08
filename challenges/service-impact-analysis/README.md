# Service impact

A change detector confuses neighboring path prefixes and reports incomplete downstream impact. Repair path semantics and complete the impact graph.

## Contract

Paths are absolute case-sensitive POSIX strings. Collapse repeated slashes; remove trailing slash except root. Reject . or .. segments. ancestor(a,b) is true for equal paths or a directory-boundary descendant; root contains all paths. watched maps service ids to watched paths. A file change affects watchers whose path is an ancestor of the file; deleting a directory also affects watched descendants. depends[A] lists services A depends on; if B is affected and A depends on B, A is affected. Return sorted unique service ids. Validate unknown dependency ids and all paths before computing; never mutate input.

## Getting started

```sh
pip install -r requirements.txt
pytest -q
```

Start with README.md, contracts.py, engine.py and tests/test_engine.py. Preserve public signatures and the frozen tests. For extra experiments use a candidate-owned scratch.py. Do not change runner configuration to obtain a pass.

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: Path ancestry uses component boundaries; dependency impact propagates from dependency to dependent.

### Part 1 — Repair path semantics

Normalize roots and slash forms while distinguishing watched-path ancestry from a bare string prefix.

Evidence to show:

- Normalize root/slash forms and honor path-component boundaries.

### Part 2 — Propagate impact

Handle changed files/deleted subtrees, reverse edges, cycles and unknown-service rejection.

Evidence to show:

- Deletion matches watched descendants; reverse dependency closure terminates through cycles and rejects unknown services.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- Repeated normalized deletion must preserve scope boundaries; deleting root affects every watched service.

### Part 4 — Changed requirement — optional discussion

Add conditional dependencies enabled by environment. Define the active graph before traversal and show how using the union of all environments would overstate impact.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
