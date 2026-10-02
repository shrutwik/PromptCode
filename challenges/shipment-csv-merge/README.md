# Shipment CSV Merge

## Scenario
Nightly CSV batches merge into timelines and quantities.

## Steps
The task opens one step at a time. Run the tests, then open the next step.

## Getting started
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
