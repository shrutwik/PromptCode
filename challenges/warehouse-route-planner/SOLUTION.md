# SOLUTION — warehouse-route-planner

## Underlying invariant

A position is not the complete state when permissions change during traversal. Separate display output from topology and search state.

## Investigation and reference repair

Run the starter first, distinguish the initial defect from incomplete checkpoints, and map a test observation to its contract. Implement each checkpoint without weakening the supplied tests. Test-only reviewed source is in backend/tests/expansion_reference_fixtures.py and never goes into candidate delivery.

Initial faulty edit locations:

- engine.py: `if cells[r][c] == '.':`.
- engine.py: `start,end=endpoints(rows)`.

## Reference approach and limits

Use breadth-first search over (position, badge mask), enqueueing neighbors in U/R/D/L order. Collect a badge before recording the destination state and check a gate against the incoming inventory. Store forbidden edges as directed pairs. Rendering operates on a copy and replaces only ordinary floor cells. With V cells and K badge types, there are at most V·2^K states; the supplied reference copies paths, so its total work and memory also depend on path length. Parent pointers avoid that extra copying.

## Checkpoint evidence

1. Repair endpoint-preserving rendering. Ask for the invariant, a counterexample and observed verification.
2. Implement shortest legal routing, including unreachable output. Ask for the invariant, a counterexample and observed verification.
3. Support badge inventory and forbidden directed edges; defend revisit behavior. Ask for the invariant, a counterexample and observed verification.

## Rubric (100)

| Criterion | Points |
|---|---:|
| Correct behavior and preserved contracts | 35 |
| Model and approach explained | 25 |
| Independent verification and counterexamples | 20 |
| AI-output review and communicated trade-offs | 20 |

This question-specific review guide does not replace the platform rubric or behavioral evidence. Do not infer understanding from a green suite alone.

## Wrong alternatives

A position-only visited set rejects a necessary revisit after collecting a badge. Treating restrictions as undirected removes legal reverse travel. Painting every visited cell destroys the endpoint and gate contract.

## Parts and reviewer evidence

Search state is position plus acquired permissions; display must preserve topology.

- Part 1 (Preserve the map): endpoint-markers, invalid-grid.
- Part 2 (Route with permissions): short-path, two-badges, reusable-badge, unreachable.
- Part 3 (Pressure-test the model): gate-before-badge, reverse-edge-allowed, badge-revisit.

Part 3 checks this contract property: A coordinate must be revisited with a different permission inventory. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: A cell is visited once regardless of newly acquired badges. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: Give floor cells different movement costs. Explain why FIFO BFS no longer guarantees minimum cost and how state identity, tie rules and the independent oracle change. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: Why can a shortest route revisit a cell? A: The cell with a new badge mask is a different state and may unlock an exit route.
2. Q: Why does BFS establish shortestness here? A: Every legal move costs one; FIFO layers enumerate increasing move count. Neighbor order resolves equal-length ties.
3. Q: When is a gate checked and a badge collected? A: Check permission before entering a gate; add a collected badge to the next state before deduplication.
4. Q: How can rendering corrupt subsequent search? A: Replacing S, E or permission tiles changes topology or loses endpoint identity; preserve them and the input grid.
