# Worker dispatch

A worker pool mishandles jobs arriving at a completion boundary and forgets queued work. Complete deterministic dispatch without changing FIFO arrival order.

## Contract

k is a positive integer; jobs are (id,arrival,duration), ids unique, arrival>=0 and duration>0 integers. Sort arrivals by time then original input index. Jobs queue FIFO when all workers are busy. Release all workers with finish<=dispatch time, then prefer the smallest available worker id. Outputs follow sorted arrival order and are [id,worker,start,finish]. Reject invalid input before scheduling and do not mutate the input list.

## Getting started

```sh
pip install -r requirements.txt
pytest -q
```

Start with README.md, contracts.py, engine.py and tests/test_engine.py. Preserve public signatures and the frozen tests. For extra experiments use a candidate-owned scratch.py. Do not change runner configuration to obtain a pass.

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: Arrival eligibility, FIFO waiting order and idle-worker selection are separate orderings.

### Part 1 — Repair eligibility

Reproduce exact completion-boundary behavior and validate job identities/durations before scheduling.

Evidence to show:

- A worker finishing now is eligible; duplicate ids and invalid durations are rejected.

### Part 2 — Schedule queued work

Implement idle and busy worker management, stable arrivals, complete release and FIFO backlog handling.

Evidence to show:

- Release all eligible workers, choose the lowest idle id, and preserve stable FIFO arrival order.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- Input permutation does not reorder distinct arrivals, and a backlog remains FIFO.

### Part 4 — Changed requirement — optional discussion

Add job priorities without preempting active work. Define fairness/starvation policy and stable ties, then identify which queue and oracle must change.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
