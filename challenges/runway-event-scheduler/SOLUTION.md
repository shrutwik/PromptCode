# SOLUTION — runway-event-scheduler

## Reference approach and limits

Eligibility precedes priority. Advance through closures, then re-evaluate the ready set; a future emergency must not preempt an active flight. Half-open occupancy permits touching boundaries. The clear scan reference is quadratic in flights, with additional closure scans; a heap implementation requires consistent event ordering, not just a faster priority queue.

Reviewed implementations are in backend/tests/ranked_reference_fixtures.py and remain interviewer/test-only.

## Initial incident

`engine.py` contains the faulty change `a<=d and c<=b`. Repair the contract rather than changing expectations.

The candidate also implements schedule from the supplied validation and overlap helper.

## Independent evidence

Eight server-owned observation probes cover this family; expected values never enter the candidate command. Two plausible wrong repairs are checked separately. Rendered frontend behavior retains explicit reviewer requirements even when the visible suite passes.

## Rubric (100)

Correct behavior and preservation: 35; model and explanation: 25; independent verification: 20; AI-output review and trade-offs: 20. This guide does not replace the platform rubric.

## Parts and reviewer evidence

Ready-set eligibility precedes priority; active occupancy is non-preemptive and half-open.

- Part 1 (Repair occupancy boundaries): boundary, closure-touch.
- Part 2 (Schedule eligible flights): priority, emergency, no-preemption, closure-fit, reselect.
- Part 3 (Pressure-test the model): cancel-at-dispatch, cancel-during-closure.

Part 3 checks this contract property: A cancellation that arrives while the runway is closed must be applied before selecting the delayed flight. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: Cancellations only need checking before a closure, not after simulated time advances through it. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: Add a second runway with its own closures and eligible flight types. Define assignment and tie policy jointly; duplicating a one-runway queue can violate global readiness and exclusion. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: Can a future emergency outrank a ready landing? A: Only after arrival; first establish eligibility, then apply priority to the ready set.
2. Q: What changes when a closure delays dispatch? A: Advance to the closure end and re-evaluate arrivals, cancellations and priorities before committing a flight.
3. Q: Can a flight end exactly at closure start? A: Yes; both occupancy and closure use half-open intervals.
4. Q: What does cancellation at dispatch do? A: It removes a waiting flight; it cannot undo or preempt an already-started occupancy.
