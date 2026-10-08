# Period boundary

You are on subscriptions. A customer canceled exactly when the billing period rolled, and the books treated that instant as still inside the period.

Support thinks the Chicago clock display is wrong again. The credit is computed from the stored period and the cancel instant. The display helper only formats that instant.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

The instant at period end is outside the period and credits nothing. The instant at period start is inside. A cancel in the middle of the period still gets a credit. A cancel before the period credits nothing.

The tests that already describe those cases stay as they are. Leave them alone and make the boundary agree with them.

## Getting started

```bash
pip install -r requirements.txt
pytest -q
```

## Investigation checkpoints

This ticket tests: A stored instant has one period owner under half-open intervals; display timezone is separate from billing identity. Verification focus: Check start, end, adjacent periods, equivalent offsets and microseconds, alongside an exact midpoint monetary calculation. Checkpoint 1: Reproduce the reported behavior and state the contract invariant. Checkpoint 2: Repair the smallest relevant path and verify preservation on success and rejection. Checkpoint 3: Defend your change with a counterexample and discuss the explicitly optional changed requirement.

## Optional review extension

Discuss a daylight-saving transition or non-monthly period using instants and elapsed duration; keep the baseline period contract. This is discussion-only and does not alter baseline acceptance tests. Keep the supplied tests and configuration intact; use scratch.py or scratch.ts for independent experiments. Explain what you asked the assistant to do and which assumption you verified.
