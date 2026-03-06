# Benchmark Pack

This directory contains the deterministic benchmark pack used for scoring-drift
and reproducibility gates.

## Files

- `benchmark_cases.json`: 100 benchmark cases across profiles:
  - `strong`
  - `average`
  - `brittle`
  - `gaming`

## Regenerate Pack

```bash
cd backend
python -m scripts.build_benchmark_pack
```

## Run Reproducibility Gate

```bash
cd backend
python -m scripts.run_reproducibility_gate --repeats 10 --stddev-threshold 0.03
```

## Run Regression Gate

```bash
cd backend
python -m scripts.run_evaluator_regression_gate
```

Gate conditions:

- Per-case repeated overall score standard deviation must be `<= 0.03`
- Mean repeated score per case must remain within each case's expected score band
