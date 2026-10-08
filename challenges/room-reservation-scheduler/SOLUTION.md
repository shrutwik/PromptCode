# SOLUTION — room-reservation-scheduler

## Underlying invariant

A correct overlap helper is not enough: finding and committing a reservation must share one atomic boundary.

## Investigation and reference repair

Run the starter first, distinguish the initial defect from incomplete checkpoints, and map a test observation to its contract. Implement each checkpoint without weakening the supplied tests. Test-only reviewed source is in backend/tests/expansion_reference_fixtures.py and never goes into candidate delivery.

Initial faulty edit locations:

- engine.py: `start=earliest`.
- contracts.py: `a[0]<=b[1] and b[0]<=a[1]`.

## Reference approach and limits

Use half-open intervals. Sort a copy and scan their union, advancing the cursor with max(cursor, booking_end) so nested bookings cannot move it backward. Return the earliest gap large enough within the requested bounds, including one ending exactly at the limit. Hold a lock across finding a slot and inserting the reservation. Sorting is O(n log n), a gap scan O(n); the reference re-sorts during reservation and serializes reservations through one scheduler lock.

## Checkpoint evidence

1. Repair overlap semantics. Ask for the invariant, a counterexample and observed verification.
2. Find earliest gaps across nested and unsorted bookings. Ask for the invariant, a counterexample and observed verification.
3. Keep bookings sorted and reserve atomically for concurrent callers. Ask for the invariant, a counterexample and observed verification.

## Rubric (100)

| Criterion | Points |
|---|---:|
| Correct behavior and preserved contracts | 35 |
| Model and approach explained | 25 |
| Independent verification and counterexamples | 20 |
| AI-output review and communicated trade-offs | 20 |

This question-specific review guide does not replace the platform rubric or behavioral evidence. Do not infer understanding from a green suite alone.

## Wrong alternatives

Inclusive overlap rejects adjacent bookings. Assigning cursor directly to each end creates false gaps inside nested intervals. Locking find and insertion separately lets two callers reserve the same gap.

## Parts and reviewer evidence

A calendar is an interval union; find and insert form one atomic reservation.

- Part 1 (Repair interval boundaries): boundary-helper, invalid-window.
- Part 2 (Find and reserve a gap): gap-exact-fit, overlapping-union, upper-bound, sorted-insert, atomic-reserve, input-copy.
- Part 3 (Pressure-test the model): failed-reserve-preserves.

Part 3 checks this contract property: An unavailable reservation leaves the calendar intact; a later exact adjacent slot remains bookable. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: An unsuccessful reservation may still insert a placeholder or change an occupied frontier. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: Add cancellation and rescheduling by reservation id. Define which reservation is released and ensure a failed reschedule restores the original slot atomically. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: Do [1,2) and [2,3) overlap? A: No; the common endpoint is excluded from the first interval.
2. Q: Why take the maximum booking end? A: A smaller nested booking must not move the occupied frontier backward.
3. Q: Can a booking finish exactly at latest_end? A: Yes; the bounded contract includes that completion boundary.
4. Q: Which operations form the atomic reservation? A: Gap search and insertion together, so a second caller observes the first reservation.
