# PromptCode Scoring Specification (v1)

This document defines the scoring contract used by the evaluator for reproducible, auditable, and company-trustable results.

## Evaluation Runs

Each submission is evaluated across a run plan:

- `clean`: base challenge input
- `hidden_clean`: private holdout inputs (if configured in `config.hidden_tests`)
- `perturbed`: normal noise perturbations
- `adversarial`: hard perturbations

Each run records:

- `run_type`, `run_index`
- pass/fail status
- accuracy score
- schema validity
- cost/tokens/latency/calls/retries
- deterministic metadata (`seed`, perturbation type/version)

## Pass Criteria

A run is `pass` if all are true:

- run succeeded
- accuracy >= `0.80`
- schema validity check passed

## Aggregate Metrics

Metrics are in `[0.0, 1.0]`:

- `accuracy`: mean of clean + hidden_clean accuracies
- `edge_case_handling` (robustness): pass-rate blend from perturbed/adversarial runs
- `reliability`: consistency across all run accuracies
- `efficiency`: quality-gated frontier using tokens/cost/latency/calls vs budgets
- `prompt_quality`: prompt engineering quality from telemetry prompts
- `orchestration`: retry/redundancy/validation/error-handling penalties
- `rule_adherence`: blended schema-valid rate + run pass rate
- `calibration`: confidence alignment score (ECE/Brier fallback to neutral if absent)

`code_quality` is tracked in report details and diagnostics.

## Overall Score Formula

Weights:

- accuracy: 0.35
- robustness: 0.15
- reliability: 0.10
- efficiency: 0.15
- prompt_quality: 0.10
- orchestration: 0.10
- calibration: 0.05

## Hard Gates / Caps

- If `accuracy < 0.40`, cap overall to `0.55`
- If `rule_adherence < 0.50`, cap overall to `0.50`
- Anti-gaming trigger caps overall to `0.45`
- Hardcoded/no-LLM patterns zero quality metrics

## Confidence and Uncertainty

Report includes confidence intervals:

- mean CI for clean accuracy
- mean CI for run accuracy
- Wilson CI for run pass-rate

## Auditability

Each report includes:

- `evaluation_config` (seed, perturbation version, run counts, scoring weights)
- `audit_trail` event log
- per-run metadata and outcomes

This enables deterministic replay and post-hoc auditing.
