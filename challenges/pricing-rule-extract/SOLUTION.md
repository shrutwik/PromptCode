# SOLUTION — pricing-rule-extract

## Root cause
Not a bug — behavior-preserving extract. Risk: reorder rules or change rounding.

## Investigation path
Goldens pass → move loop into applyRules → quote delegates.

## Reference implementation
Implement full loop in `applyRules`; `quote` returns `applyRules(input.baseCents, input.rules)`.

## Wrong alternatives
Input-order application; Math.floor discounts.

## AI failure modes
1. Reorder rules to simplify.
2. Break quote API / applied codes.

## Edge cases
Empty rules; zero base; stacked percent+amount+surcharge.

## Verification
`npm test` — zero expectation edits.

## Complexity
Medium, 25–30 min.

## Expected Event Timeline
| t | Event |
|---|---|
| 0–5 | Run goldens |
| 5–20 | Extract carefully |
| 20–30 | Confirm identical |

## Positive signals
Mechanical move; cites invariants.

## Negative signals
Edits golden expectations.

## Recovery signals
Reverts rounding experiment.

## Interviewer Observations
Watch helpful rule-order changes.

## Rubric (100)
| ID | Criterion | Pts |
|---|---|---|
| A | Extract applyRules | 20 |
| B | quote delegates | 15 |
| C | Ordering preserved | 25 |
| D | Rounding preserved | 20 |
| E | Goldens untouched | 10 |
| F | Scope | 5 |
| G | Explanation | 5 |

## Derived Timeline Metrics
Extract <20m; continuously green.

## Defend-Your-Code (4)
1. Q: Why sort type then code? A: Existing semantics.
2. Q: Why half-up? A: money.roundHalfUp.
3. Q: Surcharge first? A: Changes goldens — forbidden.
4. Q: Keep applied? A: Audit trail.

## Deeper assessment insight

Behavior-preserving extraction includes arithmetic order, rounding and the direction of delegation.

Preserve type order and code order within a type, half-up rounding, applied codes, input immutability and the final floor. Inspect quote-to-applyRules delegation.

Plausible wrong repair: Implementing applyRules as a wrapper around quote preserves outputs but does not extract the loop from quote. Ask the candidate for a concrete failing example, not just an assertion that the shortcut is bad.

Changed requirement: Discuss adding a new rule type while retaining old golden outputs and explicit ordering; do not change baseline cents. Keep this separate from baseline scoring and record the candidate reasoning and verification evidence.
