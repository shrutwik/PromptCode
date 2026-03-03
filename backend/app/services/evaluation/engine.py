"""Evaluation engine — orchestrates multiple sandbox runs and scoring.

Weight system (8 dimensions):
  - accuracy:           0.20  (did they get the right answer?)
  - prompt_quality:     0.20  (how well did they talk to the AI?)
  - rule_adherence:     0.15  (did they follow challenge-specific rules?)
  - efficiency:         0.10  (how cheaply / token-efficiently?)
  - reliability:        0.10  (how consistently across runs?)
  - orchestration:      0.10  (how cleanly did they call the LLM?)
  - code_quality:       0.10  (how well-structured is their code?)
  - edge_case_handling: 0.05  (how well do they handle noisy/adversarial input?)
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any

from app.core.config import get_settings
from app.services.evaluation.code_analysis import analyze_code, score_code_quality
from app.services.evaluation.perturbation import perturb_adversarial, perturb_normal
from app.services.evaluation.prompt_quality import score_prompt_quality
from app.services.evaluation.scorer import (
    score_accuracy,
    score_efficiency,
    score_orchestration,
    score_reliability,
)
from app.services.sandbox.runner import SandboxResult, run_in_sandbox

logger = logging.getLogger(__name__)
settings = get_settings()

SCORE_WEIGHTS = {
    "accuracy": 0.20,
    "prompt_quality": 0.20,
    "rule_adherence": 0.15,
    "efficiency": 0.10,
    "reliability": 0.10,
    "orchestration": 0.10,
    "code_quality": 0.10,
    "edge_case_handling": 0.05,
}


class EvaluationResult:
    def __init__(
        self,
        *,
        accuracy: float,
        prompt_quality: float,
        rule_adherence: float,
        efficiency: float,
        reliability: float,
        orchestration: float,
        code_quality: float,
        edge_case_handling: float,
        overall: float,
        cost_usd: float,
        latency_ms: float,
        llm_calls: int,
        runs: list[dict[str, Any]],
        prompt_quality_details: dict[str, Any],
        code_analysis_details: dict[str, Any],
        hardcoded: bool = False,
    ):
        self.accuracy = accuracy
        self.prompt_quality = prompt_quality
        self.rule_adherence = rule_adherence
        self.efficiency = efficiency
        self.reliability = reliability
        self.orchestration = orchestration
        self.code_quality = code_quality
        self.edge_case_handling = edge_case_handling
        self.overall = overall
        self.cost_usd = cost_usd
        self.latency_ms = latency_ms
        self.llm_calls = llm_calls
        self.runs = runs
        self.prompt_quality_details = prompt_quality_details
        self.code_analysis_details = code_analysis_details
        self.hardcoded = hardcoded

    def to_report(self, submission_id: str) -> dict[str, Any]:
        report: dict[str, Any] = {
            "submission_id": submission_id,
            "accuracy": self.accuracy,
            "prompt_quality": self.prompt_quality,
            "rule_adherence": self.rule_adherence,
            "efficiency": self.efficiency,
            "reliability": self.reliability,
            "orchestration": self.orchestration,
            "code_quality": self.code_quality,
            "edge_case_handling": self.edge_case_handling,
            "overall": self.overall,
            "cost_usd": round(self.cost_usd, 6),
            "latency_ms": round(self.latency_ms, 2),
            "llm_calls": self.llm_calls,
            "prompt_quality_details": self.prompt_quality_details,
            "code_analysis_details": self.code_analysis_details,
            "runs": self.runs,
        }
        if self.hardcoded:
            report["disqualified"] = True
            report["disqualification_reason"] = (
                "Submission appears to contain hardcoded answers rather than "
                "using AI to solve the problem. All scores have been zeroed."
            )
        return report


def evaluate_submission(
    code: str,
    entrypoint: str,
    challenge_config: dict[str, Any],
) -> EvaluationResult:
    """Run a full evaluation: sandbox runs, then all six scoring dimensions."""

    ground_truth = challenge_config.get("ground_truth", "")
    if isinstance(ground_truth, (list, dict)):
        ground_truth = json.dumps(ground_truth)
    accuracy_mode = challenge_config.get("accuracy_mode", "json")
    base_inputs = challenge_config.get("inputs", {})
    challenge_description = challenge_config.get("description", "")

    run_records: list[dict[str, Any]] = []
    accuracies: list[float] = []
    all_telemetry: list[dict[str, Any]] = []
    total_tokens = 0
    total_cost = 0.0
    total_latency = 0.0
    total_calls = 0
    total_retries = 0

    # --- Normal runs with perturbations ---
    for i in range(settings.evaluation_normal_runs):
        seed = random.randint(0, 2**31)
        perturbed = perturb_normal(base_inputs, seed)
        result = run_in_sandbox(
            code, entrypoint, challenge_config, input_overrides=perturbed
        )
        record = _process_run(result, ground_truth, accuracy_mode, "normal", i)
        run_records.append(record)
        accuracies.append(record["accuracy"])
        all_telemetry.extend(result.telemetry)
        total_tokens += record["tokens_total"]
        total_cost += record["cost_usd"]
        total_latency += record["latency_ms"]
        total_calls += record["llm_calls"]
        total_retries += record["retries"]

    # --- Adversarial runs ---
    for i in range(settings.evaluation_adversarial_runs):
        seed = random.randint(0, 2**31)
        perturbed = perturb_adversarial(base_inputs, seed)
        result = run_in_sandbox(
            code, entrypoint, challenge_config, input_overrides=perturbed
        )
        record = _process_run(result, ground_truth, accuracy_mode, "adversarial", i)
        run_records.append(record)
        accuracies.append(record["accuracy"])
        all_telemetry.extend(result.telemetry)
        total_tokens += record["tokens_total"]
        total_cost += record["cost_usd"]
        total_latency += record["latency_ms"]
        total_calls += record["llm_calls"]
        total_retries += record["retries"]

    # --- Hardcode detection ---
    # If the code produces high accuracy but makes zero LLM calls, the user
    # likely hardcoded the answer or leaked the ground truth.
    hardcoded = _detect_hardcoding(
        total_calls=total_calls,
        accuracies=accuracies,
        code=code,
        ground_truth=ground_truth,
    )

    # --- Static code analysis ---
    code_analysis_result = analyze_code(code)
    code_quality_result = score_code_quality(code_analysis_result)

    # --- Prompt quality (LLM-as-judge) ---
    pq_result = score_prompt_quality(all_telemetry, challenge_description)

    # --- Scoring ---
    acc = round(sum(accuracies) / len(accuracies), 4) if accuracies else 0.0
    pq = round(pq_result.get("overall", 0.0), 4)
    eff = score_efficiency(total_tokens, total_cost)
    rel = score_reliability(accuracies)
    orch = score_orchestration(
        total_calls,
        total_retries,
        expected_calls=challenge_config.get("expected_calls", 3),
        code_analysis=code_quality_result,
    )
    cq = round(code_quality_result.get("score", 0.5), 4)

    if hardcoded:
        logger.warning("Hardcoded answer detected — zeroing all scores")
        acc = pq = eff = rel = orch = cq = 0.0

    overall = round(
        acc * SCORE_WEIGHTS["accuracy"]
        + pq * SCORE_WEIGHTS["prompt_quality"]
        + eff * SCORE_WEIGHTS["efficiency"]
        + rel * SCORE_WEIGHTS["reliability"]
        + orch * SCORE_WEIGHTS["orchestration"]
        + cq * SCORE_WEIGHTS["code_quality"],
        4,
    )

    return EvaluationResult(
        accuracy=acc,
        prompt_quality=pq,
        efficiency=eff,
        reliability=rel,
        orchestration=orch,
        code_quality=cq,
        overall=overall,
        cost_usd=total_cost,
        latency_ms=total_latency,
        llm_calls=total_calls,
        runs=run_records,
        prompt_quality_details=pq_result,
        code_analysis_details=code_quality_result,
        hardcoded=hardcoded,
    )


def _detect_hardcoding(
    total_calls: int,
    accuracies: list[float],
    code: str,
    ground_truth: str,
) -> bool:
    """Detect if the user hardcoded the answer instead of using AI.

    Signals:
    1. Zero LLM calls but high accuracy → definitely hardcoded
    2. Ground truth strings embedded literally in the source code
    3. Very few LLM calls with suspiciously perfect accuracy across
       ALL runs including adversarial (real AI solutions degrade on noisy input)
    """
    mean_acc = sum(accuracies) / len(accuracies) if accuracies else 0.0

    if total_calls == 0 and mean_acc > 0.3:
        return True

    if total_calls == 0:
        return True

    code_lower = code.lower()
    try:
        gt = json.loads(ground_truth) if isinstance(ground_truth, str) else ground_truth
    except (json.JSONDecodeError, TypeError):
        gt = None

    if gt:
        embedded_count = _count_gt_fragments_in_code(gt, code_lower)
        if embedded_count >= 3:
            return True

    if total_calls <= 1 and mean_acc > 0.95 and len(accuracies) >= 5:
        all_perfect = all(a > 0.9 for a in accuracies)
        if all_perfect:
            return True

    return False


def _count_gt_fragments_in_code(gt: Any, code_lower: str) -> int:
    """Count how many ground truth values appear literally in the source."""
    count = 0

    if isinstance(gt, dict):
        for v in gt.values():
            count += _count_gt_fragments_in_code(v, code_lower)
    elif isinstance(gt, list):
        for item in gt:
            count += _count_gt_fragments_in_code(item, code_lower)
    elif isinstance(gt, str) and len(gt) > 5:
        if gt.lower() in code_lower:
            count += 1
    elif isinstance(gt, (int, float)):
        if str(gt) in code_lower and gt not in (0, 1, 0.0, 1.0):
            count += 1

    return count


def _process_run(
    result: SandboxResult,
    ground_truth: str,
    accuracy_mode: str,
    run_type: str,
    run_index: int,
) -> dict[str, Any]:
    telemetry = result.telemetry
    tokens = sum(r.get("tokens_total", 0) for r in telemetry)
    cost = sum(r.get("cost_usd", 0.0) for r in telemetry)
    latency = sum(r.get("latency_ms", 0.0) for r in telemetry)
    calls = len(telemetry)
    retries = sum(1 for r in telemetry if r.get("retry_index", 0) > 0)

    acc = 0.0
    if result.success:
        acc = score_accuracy(result.output.strip(), ground_truth, mode=accuracy_mode)

    return {
        "run_type": run_type,
        "run_index": run_index,
        "success": result.success,
        "accuracy": round(acc, 4),
        "tokens_total": tokens,
        "cost_usd": round(cost, 6),
        "latency_ms": round(latency, 2),
        "llm_calls": calls,
        "retries": retries,
        "error": result.error,
    }
