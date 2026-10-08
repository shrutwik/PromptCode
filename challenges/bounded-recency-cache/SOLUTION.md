# SOLUTION — bounded-recency-cache

## Underlying invariant

Recency is an invariant, not insertion order. Atomic creation concerns the entire read/compute/write sequence, including cached None.

## Investigation and reference repair

Run the starter first, distinguish the initial defect from incomplete checkpoints, and map a test observation to its contract. Implement each checkpoint without weakening the supplied tests. Test-only reviewed source is in backend/tests/expansion_reference_fixtures.py and never goes into candidate delivery.

Initial faulty edit locations:

- engine.py: `self.data.move_to_end(key)`.
- engine.py: `validate_capacity(capacity)`.
- engine.py: `def get_or_put(self,key,factory):`.

## Reference approach and limits

Use an ordered mapping from least to most recent. Both successful reads and writes move an entry to the recent end; misses do not alter order. Resize evicts oldest entries until the bound holds, including capacity zero. Lock the complete get-or-create operation and distinguish membership from a cached None. Factory exceptions propagate without inserting a value. Reads/writes are amortized O(1), resizing costs O(evictions); the simple reference holds a shared lock during the factory and serializes unrelated creation.

## Checkpoint evidence

1. Repair read promotion and eviction. Ask for the invariant, a counterexample and observed verification.
2. Implement resize, replacement and zero capacity. Ask for the invariant, a counterexample and observed verification.
3. Make get_or_put atomic and preserve state when the factory fails. Ask for the invariant, a counterexample and observed verification.

## Rubric (100)

| Criterion | Points |
|---|---:|
| Correct behavior and preserved contracts | 35 |
| Model and approach explained | 25 |
| Independent verification and counterexamples | 20 |
| AI-output review and communicated trade-offs | 20 |

This question-specific review guide does not replace the platform rubric or behavioral evidence. Do not infer understanding from a green suite alone.

## Wrong alternatives

Using truthiness for a hit treats None as a miss. Locking only insertion allows duplicate factories. Evicting on get misses changes order without a successful access.

## Parts and reviewer evidence

Successful reads/writes promote recency; compound creation and validation must preserve the bound.

- Part 1 (Restore recency): read-recency, none-is-cached, invalid-construction.
- Part 2 (Resize and create safely): shrink-oldest, grow-keeps-order, zero-capacity, concurrent-factory, factory-retry.
- Part 3 (Pressure-test the model): invalid-resize-preserves.

Part 3 checks this contract property: A rejected resize must preserve both the capacity and recency order used by the next eviction. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: It is safe to replace capacity or evict entries before validating a resize. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: Add TTL with an injected monotonic clock. Define the exact expiration boundary, whether expired reads affect recency, and how expiry interacts with atomic factories and resize. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: Is a cached None a miss? A: No; use key membership independently from the stored value.
2. Q: What happens after a factory raises? A: The key remains absent and a later call may retry; the lock is released.
3. Q: Where is atomicity required? A: Across the membership check, factory call and insertion so concurrent callers do not create twice.
4. Q: What is the lock trade-off? A: A shared lock is simple and correct but serializes unrelated factories; per-key coordination requires additional lifecycle rules.
