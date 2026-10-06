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
