# Pricing rules

You are in pricing. Quotes are correct, and finance trusts the golden cents. The rule loop is buried inside `quote()`, and the next pricing change is unsafe until that loop can be read on its own.

Percent-off and amount-off do not commute once you round.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

Add `applyRules(baseCents, rules)`. It applies `percent_off`, then `amount_off`, then `surcharge_percent`, with the same half-up rounding, and returns the same `finalCents` and applied codes as `quote()`.

`quote()` calls `applyRules` and keeps its current signature. A negative result floors at 0. An empty rule list returns the base.

If a golden cent moves, the extract is wrong. Leave the expectations alone.

## Getting started

```bash
npm install
npm test
```
