# Shipment CSV

You own the nightly shipment merge. Warehouse drops two CSV files that landed out of order. A shipment timeline showed a later status before an earlier one, and a quantity that should have been counted once was counted twice.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

Events from separate files come out in timestamp order for each shipment. The same `event_id` in two files counts once. Two events with the same status and different ids both stay, in timestamp order.

A teammate thinks a comma inside a CSV field broke the parser. That is a hypothesis.

## Getting started

```bash
pip install -r requirements.txt
pytest -q
```
