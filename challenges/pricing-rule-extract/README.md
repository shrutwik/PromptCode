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

## Investigation checkpoints

This ticket tests: Behavior-preserving extraction includes arithmetic order, rounding and the direction of delegation. Verification focus: Preserve type order and code order within a type, half-up rounding, applied codes, input immutability and the final floor. Inspect quote-to-applyRules delegation. Checkpoint 1: Reproduce the reported behavior and state the contract invariant. Checkpoint 2: Repair the smallest relevant path and verify preservation on success and rejection. Checkpoint 3: Defend your change with a counterexample and discuss the explicitly optional changed requirement.

## Optional review extension

Discuss adding a new rule type while retaining old golden outputs and explicit ordering; do not change baseline cents. This is discussion-only and does not alter baseline acceptance tests. Keep the supplied tests and configuration intact; use scratch.py or scratch.ts for independent experiments. Explain what you asked the assistant to do and which assumption you verified.
