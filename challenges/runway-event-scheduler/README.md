# Runway simulation

schedule(flights,closures=(),cancellations=None) returns [id,start,end] occupancy records. Each flight is a dict with unique nonempty string id, nonnegative integer arrival, positive integer duration, kind landing or takeoff, and optional boolean emergency (default false). One runway, no preemption. At each free instant choose among arrived, not cancelled flights: emergency first (regardless of kind), then ordinary landing, then takeoff; ties by arrival then id. Cancellations map known ids to nonnegative integer instants and remove only flights not yet started when that instant is reached, including at dispatch. Closures are integer [start,end) with 0<=start<end; no occupancy may overlap any closure. If the selected flight cannot fit, advance to the end of the obstructing closure and re-evaluate arrivals and priorities. Finishing at closure start is legal. Reject invalid input and preserve all supplied collections. This is a toy simulation.

## Verification

Run `pytest -q`. Start with the listed entry files and tests; starters intentionally contain a defect. A passing suite is evidence, not a substitute for explaining the invariant.

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: Ready-set eligibility precedes priority; active occupancy is non-preemptive and half-open.

### Part 1 — Repair occupancy boundaries

Validate touching closure/flight boundaries and distinguish a delayed start from overlap.

Evidence to show:

- Occupancy may end at closure start and never overlaps a closed interval.

### Part 2 — Schedule eligible flights

Implement deterministic emergency/landing/takeoff priority, non-preemption and reselection after closures.

Evidence to show:

- Only arrived flights compete; deterministic priority does not preempt active occupancy, and closures trigger reselection.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- A cancellation that arrives while the runway is closed must be applied before selecting the delayed flight.

### Part 4 — Changed requirement — optional discussion

Add a second runway with its own closures and eligible flight types. Define assignment and tie policy jointly; duplicating a one-runway queue can violate global readiness and exclusion.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
