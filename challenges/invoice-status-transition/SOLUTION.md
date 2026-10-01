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

## Defend-Your-Code (4)
1. Q: Why not timezone? A: Not on mutation path.
2. Q: Keep paid→void? A: Encoded finance need.
3. Q: 409 vs 400? A: Conflict with resource state.
4. Q: Admin reopen? A: Out of scope / dangerous.
