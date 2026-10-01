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

## Defend-Your-Code (4)
1. Q: Why map new objects? A: Avoid shared mutation.
2. Q: Await then update? A: Matches pattern.
3. Q: Redux? A: Unnecessary.
4. Q: unreadCount? A: Derived from items.
