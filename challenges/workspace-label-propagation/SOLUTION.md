# SOLUTION — workspace-label-propagation

## Root cause
API omits labelIds; UI sets selected to [].

## Investigation path
Fail round-trip + client test → app.ts + TicketLabels.tsx.

## Reference implementation
Include `labelIds` on GET/PUT responses; `setSelected(ticket.labelIds ?? [])`.

## Wrong alternatives
Free-text redesign.

## AI failure modes
1. Scope explosion.
2. API-only without UI load sync.

## Edge cases
Empty array; cross-workspace rejected.

## Verification
`npm test`

## Complexity
Medium, 30–35 min. Progressive A/B/C.

## Expected Event Timeline
| t | Event |
|---|---|
| 0–5 | Read parts |
| 5–15 | Fix API |
| 15–25 | Wire UI |
| 25–35 | Green |

## Positive signals
Additive field.

## Negative signals
Free-text rewrite.

## Recovery signals
Checks payload after UI-only attempt.

## Interviewer Observations
Wrong-assumption handling.

## Rubric (100)
| ID | Criterion | Pts |
|---|---|---|
| A | Persist | 15 |
| B | API | 25 |
| C | UI | 25 |
| D | Validation | 10 |
| E | Scope | 10 |
| F | Tests | 10 |
| G | Comm | 5 |

## Derived Timeline Metrics
API <15m; full <35m.

## Defend-Your-Code (4)
1. Q: Free-text? A: Workspace labels fit.
2. Q: PUT returns ids? A: Client sync.
3. Q: Empty array? A: Explicit none.
4. Q: Authz? A: Out of scope.

## Deeper assessment insight

Validated workspace ids must survive storage, response serialization and later component hydration.

Verify selected checkboxes after PUT, GET and remount; clear all labels; reject mixed valid/foreign lists without changing prior labels.

Plausible wrong repair: Updating only a response object or optimistic component state does not prove the next read contains the labels. Ask the candidate for a concrete failing example, not just an assertion that the shortcut is bad.

Changed requirement: Discuss deleting a label while a user edits a ticket and how to expose the conflict; do not silently add that behavior to the baseline. Keep this separate from baseline scoring and record the candidate reasoning and verification evidence.
