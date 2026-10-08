# SOLUTION — courier-payment-ledger

## Underlying invariant

Money rounding is a record-level policy; payment idempotency and the identity of an active driver are separate invariants.

## Investigation and reference repair

Run the starter first, distinguish the initial defect from incomplete checkpoints, and map a test observation to its contract. Implement each checkpoint without weakening the supplied tests. Test-only reviewed source is in backend/tests/expansion_reference_fixtures.py and never goes into candidate delivery.

Initial faulty edit locations:

- engine.py: `return cents_for(self.rates[driver],start,end)`.
- engine.py: `due=[id for id,x in self.deliveries.items() if id not in self.paid and x[2]<=cutoff]`.

## Reference approach and limits

Compute each delivery amount with exact integer arithmetic and half-up rounding, then sum those amounts. Delivery ids identify immutable records; identical replay is a no-op and conflicting reuse is rejected. Mark only completed eligible deliveries paid. For activity, process half-open interval events and keep a count per driver so overlapping deliveries do not count a driver twice. Ledger scans are linear; the reference activity sweep sorts events and scans driver counts, so worst-case work is O(n log n + n·d), with d drivers.

## Checkpoint evidence

1. Correct second-level payout precision. Ask for the invariant, a counterexample and observed verification.
2. Implement totals and cutoff payments without duplicate effects. Ask for the invariant, a counterexample and observed verification.
3. Compute peak distinct-driver activity with touching intervals. Ask for the invariant, a counterexample and observed verification.

## Rubric (100)

| Criterion | Points |
|---|---:|
| Correct behavior and preserved contracts | 35 |
| Model and approach explained | 25 |
| Independent verification and counterexamples | 20 |
| AI-output review and communicated trade-offs | 20 |

This question-specific review guide does not replace the platform rubric or behavioral evidence. Do not infer understanding from a green suite alone.

## Wrong alternatives

Rounding the combined duration instead of each delivery changes cents. Paying a delivery whose start precedes the cutoff includes unfinished work. Counting active deliveries overstates distinct active drivers.

## Parts and reviewer evidence

Rounded delivery costs, successful payments and distinct-driver activity are different aggregates.

- Part 1 (Recover precise amounts): payout-precision, per-record-rounding, unknown-driver, invalid-preserves.
- Part 2 (Pay and measure activity): incremental-pay, peak-distinct, window-clipping.
- Part 3 (Pressure-test the model): conflict-preserves, nonmonotonic-cutoffs.

Part 3 checks this contract property: An earlier cutoff after a later payment cannot charge again or change ledger totals. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: An earlier cutoff can reset the payment cursor or make paid records unpaid again. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: A completed delivery is corrected after payment. Design immutable adjustment records and idempotent refunds; explain how historical receipts and current unpaid amounts differ. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: What is the unit of rounding? A: One delivery amount in integer cents; sum rounded amounts afterward.
2. Q: What does replaying an id mean? A: The same driver and interval is idempotent; different content with the same id is a conflict.
3. Q: Which deliveries belong to a cutoff payment? A: Unpaid deliveries with end ≤ cutoff; later calls cannot pay them again.
4. Q: Why is a per-driver count needed? A: A driver can have overlapping deliveries; activity begins at count zero-to-one and ends at one-to-zero.
