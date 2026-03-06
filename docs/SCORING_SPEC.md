# PromptCode Scoring Specification (v1.1)

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

## AI-Leverage Metrics

In addition to weighted overall score, evaluator computes an AI-leverage layer:

- `frontier_navigation_score`: how well quality is matched to usage (tokens/cost/latency/calls) against budget frontier
- `reliance_calibration_score`: whether model reliance is supported by validation/recovery discipline and observed run quality
- `learning_velocity_score`: iteration-to-iteration improvement efficiency (first attempt defaults to `0.5`)
- `counterfactual_baseline_overall`: baseline score from sandbox-run naive strategy on same run plan
- `leverage_gain`: `overall - counterfactual_baseline_overall`
- `ai_mastery_score`: composite of frontier navigation, reliance calibration, prompt quality, learning velocity, and leverage gain when baseline is available

Current composite weights:

- frontier_navigation: 0.30
- reliance_calibration: 0.25
- prompt_quality: 0.15
- learning_velocity: 0.15
- leverage_gain: 0.15 (counterfactual mode)

`ai_mastery_score` is currently exposed for credibility/coaching and does not replace leaderboard `overall`.
Counterfactual baseline can be toggled via `counterfactual_baseline_enabled` in challenge config.

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

## Leaderboard Eligibility Gates

A completed submission is leaderboard-eligible only if:

- reliability is above minimum policy threshold
- total evaluation tests meet minimum threshold
- prompt judge method is `llm_judge` (heuristic fallback is excluded)
- counterfactual baseline status is `ok`
- `leverage_gain >= 0.0`
- credibility score meets minimum threshold

## Confidence and Uncertainty

Report includes confidence intervals:

- mean CI for clean accuracy
- mean CI for run accuracy
- Wilson CI for run pass-rate

Report also includes `credibility`:

- score and band (`high`/`medium`/`low`)
- signal provenance (judge method, calibration samples, run depth, hidden coverage, counterfactual status, CI width, anti-gaming flags)

This indicates how trustworthy the reported score is for decision-making.

## Auditability

Each report includes:

- `evaluation_config` (seed, perturbation version, run counts, scoring weights)
- `audit_trail` event log
- per-run metadata and outcomes
- `ai_leverage` block with detailed leverage signals and methods
- `learning_effectiveness` block (`coach_hit_rate`, assessed actions, per-action deltas)

This enables deterministic replay and post-hoc auditing.
