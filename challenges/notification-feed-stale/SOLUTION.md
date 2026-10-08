# SOLUTION — notification-feed-stale

## Root cause
`markAsRead` copies a stale snapshot before await, then writes it back — concurrent calls clobber each other.

## Investigation path
Concurrency test fails → feedStore.markAsRead.

## Reference implementation
```ts
export async function markAsRead(id: string): Promise<void> {
  await markReadOnServer(id);
  items = items.map((n) => (n.id === id ? { ...n, read: true } : n));
  emit();
}
```

## Wrong alternatives
UI-only remount; mutate in place.

## AI failure modes
1. Fix component only.
2. Keep stale snapshot pattern.

## Edge cases
Overlapping Promise.all marks.

## Verification
`npm test`

## Complexity
Medium, 25–30 min.

## Expected Event Timeline
| t | Event |
|---|---|
| 0–5 | Run tests |
| 5–15 | Find stale snapshot |
| 15–25 | Fix store |
| 25–30 | Concurrency green |

## Positive signals
Immutability / closure reasoning.

## Negative signals
Blames React keys only.

## Recovery signals
Returns to store after UI-only failure.

## Interviewer Observations
Ask about concurrent marks.

## Rubric (100)
| ID | Criterion | Pts |
|---|---|---|
| A | Diagnosis | 25 |
| B | Immutable update | 20 |
| C | Concurrent marks | 20 |
| D | UI works | 10 |
| E | Scope | 10 |
| F | Explanation | 10 |
| G | Verification | 5 |

## Derived Timeline Metrics
Store <10m; green <30m.

## Parts and reviewer evidence

Each async completion merges into current state and must converge with rendered rows and badge.

- Part 1 (Establish observable state): loaded-count, one-mark, already-read.
- Part 2 (Merge concurrent successes): concurrent-marks, duplicate-concurrent-marks.
- Part 3 (Pressure-test the model): failed-mark-preserves-state, mixed-success-failure.

Part 3 checks this contract property: A failed concurrent mark must not erase two successful independent updates. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: A failed concurrent request may restore an old global snapshot and erase successful independent updates. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: A refresh started before a mark completes afterward. Define request-generation or merge semantics and prove a stale response cannot undo a successful mark; discuss which server guarantees are needed. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: Why map new objects? A: Avoid shared mutation.
2. Q: Await then update? A: Matches pattern.
3. Q: Redux? A: Unnecessary.
4. Q: unreadCount? A: Derived from items.

## Deeper assessment insight

Async completion must converge with current store state and the rendered badge.

Verify two different quick marks, repeated marks, an already-read row and a rejected request; inspect rendered rows and count together.

Plausible wrong repair: Writing an old captured list after awaiting a request can restore a row that another request already marked read. Ask the candidate for a concrete failing example, not just an assertion that the shortcut is bad.

Changed requirement: Discuss a late load response arriving after a mark and what request-generation or merge policy would mean; this remains a discussion extension. Keep this separate from baseline scoring and record the candidate reasoning and verification evidence.
