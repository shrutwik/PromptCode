# Order hold

You are on the orders API during a warehouse freeze.

Support puts an order on hold with a reason. The next read cannot say why it is held, or the hold does not survive a refresh. Orders created before this field existed are still in the database.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

`POST /orders/:id/hold` with a `hold_reason` stores that reason and returns the order as `on_hold`. The following GET returns the same reason.

`POST /orders/:id/release` returns the order as `open`.

Orders that never had a reason come back with `hold_reason` null. Money is `total_cents`, an integer.

People are blaming the metrics counter. That is a hypothesis.

## Getting started

```bash
pip install -r requirements.txt
pytest -q
```
