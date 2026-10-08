# SOLUTION — invoice-status-transition

## Root cause
`canTransition` special-cases `paid` and returns true for any non-void target, allowing paid→draft. Timezone formatting is unused on the mutation path.

## Investigation path
1. Reproduce paid→draft via `transitionInvoice` / API.
2. Trace to `statusMachine.canTransition`.
3. Confirm `timezoneFormat` only used by `describeInvoice`.

## Reference implementation
```ts
export function canTransition(from: InvoiceStatus, to: InvoiceStatus): boolean {
  if (from === to) return false;
  return ALLOWED[from].includes(to);
}
```
Regression:
```ts
it('rejects paid -> draft', () => {
  expect(canTransition('paid', 'draft')).toBe(false);
  expect(() => transitionInvoice('inv_paid', 'draft')).toThrow(/Illegal transition/);
});
```

## Wrong alternatives
- Patching timezone formatting; blocking paid→void.

## AI failure modes
1. Red-herring timezone fix while bug remains.
2. Over-restricting valid transitions.

## Edge cases
Same-status rejected; void terminal; API maps to 409.

## Verification
`npm test` after adding regression.

## Complexity
Medium, 25–30 min.

## Expected Event Timeline
| t | Event |
|---|---|
| 0–5 | Run tests, read ticket |
| 5–12 | Reproduce paid→draft |
| 12–22 | Fix machine + regression |
| 22–30 | Verify void still works |

## Positive signals
Ignores timezone after call-site check; adds regression.

## Negative signals
Rewrites date formatting first.

## Recovery signals
Returns to status machine when timezone patch fails reproduction.

## Interviewer Observations
Validates ticket causal claim before coding.

## Rubric (100)
| ID | Criterion | Pts |
|---|---|---|
| A | Root cause | 20 |
| B | Preserves valid transitions | 20 |
| C | Rejects paid→draft | 15 |
| D | Regression test | 15 |
| E | Avoids timezone churn | 10 |
| F | Scoping | 10 |
| G | Verification | 10 |

## Derived Timeline Metrics
Reproduce <10m; correct file <15m; green <30m.

## Parts and reviewer evidence

Transition legality is a directed graph; rejected writes preserve the entire stored invoice.

- Part 1 (Establish the legal graph): legal-graph, missing-distinct.
- Part 2 (Apply legal lifecycle changes): legal-api-transition, api-transition-matrix.
- Part 3 (Pressure-test the model): illegal-preserves-paid, missing-status-preserves-state, terminal-sequence-preserves.

Part 3 checks this contract property: The complete legal lifecycle must end in a terminal state whose rejected edit preserves every field. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: Blocking one paid-to-draft edge establishes a complete lifecycle and terminal-state policy. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: Two users attempt different transitions from the same revision. Design a compare-and-set/version check and explain which loser receives a conflict without overwriting the winner. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: Why not timezone? A: Not on mutation path.
2. Q: Keep paid→void? A: Encoded finance need.
3. Q: 409 vs 400? A: Conflict with resource state.
4. Q: Admin reopen? A: Out of scope / dangerous.

## Deeper assessment insight

Transition legality is a directed graph; rejected writes must preserve the entire invoice.

Use the full four-by-four transition matrix, including same-state rejection, terminal void and preservation of amount on 409.

Plausible wrong repair: Blocking every transition from paid also blocks the legal paid-to-void operation. Ask the candidate for a concrete failing example, not just an assertion that the shortcut is bad.

Changed requirement: Discuss how adding an audited reopen operation changes the graph and migration policy; it is not a baseline permission. Keep this separate from baseline scoring and record the candidate reasoning and verification evidence.
