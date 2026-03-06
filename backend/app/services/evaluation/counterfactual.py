"""Counterfactual baseline helpers for the evaluation engine."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.evaluation.constants import SCORE_WEIGHTS
from app.services.evaluation.helpers import (
    _detect_metric_gaming,
    _extract_confidence_points,
    _process_run,
    _score_constraint_adherence,
    _score_robustness,
)
from app.services.evaluation.prompt_quality import score_prompt_quality
from app.services.evaluation.reporting import (
    _apply_confidence_caps,
    _apply_overall_caps,
    _mean_confidence_interval,
)
from app.services.evaluation.scorer import (
    score_calibration,
    score_efficiency_tradeoff,
    score_orchestration,
    score_reliability,
)
from app.services.sandbox.runner import run_in_sandbox

logger = logging.getLogger(__name__)


def _evaluate_counterfactual_baseline_sync(
    *,
    run_plan: list[dict[str, Any]],
    challenge_config: dict[str, Any],
) -> dict[str, Any]:
    if not bool(challenge_config.get("counterfactual_baseline_enabled", True)):
        return {"status": "disabled", "reason": "counterfactual_baseline_disabled"}
    if not run_plan:
        return {"status": "error", "reason": "empty_run_plan"}

    try:
        challenge_description = str(challenge_config.get("description", ""))
        variants = _counterfactual_strategy_variants(challenge_config)
        variant_results: list[dict[str, Any]] = []
        for variant in variants:
            baseline_code = _build_counterfactual_baseline_code(
                challenge_config,
                challenge_description,
                strategy_prompt=variant["prompt"],
            )
            result = _run_counterfactual_candidate(
                baseline_code=baseline_code,
                run_plan=run_plan,
                challenge_config=challenge_config,
                challenge_description=challenge_description,
            )
            result["strategy_id"] = variant["id"]
            variant_results.append(result)

        ok_results = [r for r in variant_results if r.get("status") == "ok"]
        if not ok_results:
            return {
                "status": "error",
                "reason": "all_counterfactual_variants_failed",
                "variants": variant_results,
            }

        sorted_ok = sorted(ok_results, key=lambda r: float(r.get("overall") or 0.0))
        median = sorted_ok[len(sorted_ok) // 2]
        aggregate_overall = round(float(median.get("overall") or 0.0), 4)
        aggregate_raw = round(float(median.get("raw_overall") or 0.0), 4)

        merged = dict(median)
        merged["overall"] = aggregate_overall
        merged["raw_overall"] = aggregate_raw
        merged["aggregate"] = {
            "method": "median_overall",
            "variant_overalls": [
                {
                    "strategy_id": str(r.get("strategy_id") or "unknown"),
                    "overall": round(float(r.get("overall") or 0.0), 4),
                }
                for r in sorted_ok
            ],
            "selected_strategy_id": str(median.get("strategy_id") or "unknown"),
            "variants_ok": len(ok_results),
            "variants_total": len(variant_results),
        }
        merged["method"] = "sandbox_counterfactual_multi_v1"
        return merged
    except Exception as exc:
        logger.exception("Counterfactual baseline evaluation failed")
        return {"status": "error", "reason": str(exc)}


def _run_counterfactual_candidate(
    *,
    baseline_code: str,
    run_plan: list[dict[str, Any]],
    challenge_config: dict[str, Any],
    challenge_description: str,
) -> dict[str, Any]:
    run_records: list[dict[str, Any]] = []
    clean_accuracies: list[float] = []
    perturbed_accuracies: list[float] = []
    adversarial_accuracies: list[float] = []
    all_telemetry: list[dict[str, Any]] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0
    total_latency = 0.0
    total_calls = 0
    total_retries = 0

    for spec in run_plan:
        result = run_in_sandbox(
            baseline_code,
            "counterfactual_baseline.py",
            challenge_config,
            input_overrides=spec["inputs"],
        )
        record = _process_run(
            result,
            spec["ground_truth"],
            spec["accuracy_mode"],
            spec["run_type"],
            spec["run_index"],
            meta=spec.get("meta"),
        )
        run_records.append(record)
        if spec["run_type"] in ("clean", "hidden_clean"):
            clean_accuracies.append(record["accuracy"])
        elif spec["run_type"] == "perturbed":
            perturbed_accuracies.append(record["accuracy"])
        elif spec["run_type"] == "adversarial":
            adversarial_accuracies.append(record["accuracy"])

        all_telemetry.extend(result.telemetry)
        total_prompt_tokens += record["tokens_prompt"]
        total_completion_tokens += record["tokens_completion"]
        total_cost += record["cost_usd"]
        total_latency += record["latency_ms"]
        total_calls += record["llm_calls"]
        total_retries += record["retries"]

    all_accuracies = clean_accuracies + perturbed_accuracies + adversarial_accuracies
    acc = round(sum(clean_accuracies) / len(clean_accuracies), 4) if clean_accuracies else 0.0
    robustness = _score_robustness(perturbed_accuracies, adversarial_accuracies)
    rel = score_reliability(all_accuracies)
    rule_adherence = _score_constraint_adherence(run_records)
    quality_anchor = (acc * 0.5) + (robustness * 0.3) + (rel * 0.2)
    run_count = max(1, len(run_records))
    budgets = {
        "token_budget": challenge_config.get("token_budget", 12_000),
        "cost_budget_usd": challenge_config.get("cost_budget_usd", 0.20),
        "latency_budget_ms": challenge_config.get("latency_budget_ms", 30_000),
        "call_budget": challenge_config.get("call_budget", challenge_config.get("expected_calls", 3) * run_count),
    }
    eff = score_efficiency_tradeoff(
        total_tokens=total_prompt_tokens + total_completion_tokens,
        total_cost_usd=total_cost,
        total_latency_ms=total_latency,
        total_calls=total_calls,
        quality_anchor=quality_anchor,
        budgets=budgets,
    )
    pq_result = score_prompt_quality(all_telemetry, challenge_description)
    pq = round(float(pq_result.get("overall", 0.0)), 4)
    if pq_result.get("method") == "heuristic":
        pq = min(pq, 0.65)

    orch = score_orchestration(
        total_calls,
        total_retries,
        expected_calls=challenge_config.get("expected_calls", 3),
        code_analysis=None,
    )
    calibration_points = _extract_confidence_points(run_records)
    calibration_result = score_calibration(calibration_points)
    calibration = float(calibration_result.get("score", 0.5))
    calibration_samples = int(calibration_result.get("samples") or 0)
    run_accuracy_ci_half_width = float(
        _mean_confidence_interval(all_accuracies).get("half_width") or 0.0
    )

    metric_gaming = _detect_metric_gaming(
        runs=run_records,
        total_tokens=total_prompt_tokens + total_completion_tokens,
        total_calls=total_calls,
        accuracy=acc,
        robustness=robustness,
    )
    if metric_gaming["triggered"]:
        eff = min(eff, 0.25)
        orch = min(orch, 0.5)

    raw_overall = round(
        acc * SCORE_WEIGHTS["accuracy"]
        + robustness * SCORE_WEIGHTS["robustness"]
        + rel * SCORE_WEIGHTS["reliability"]
        + eff * SCORE_WEIGHTS["efficiency"]
        + pq * SCORE_WEIGHTS["prompt_quality"]
        + orch * SCORE_WEIGHTS["orchestration"]
        + calibration * SCORE_WEIGHTS["calibration"],
        4,
    )
    overall, cap_events = _apply_overall_caps(
        raw_overall=raw_overall,
        accuracy=acc,
        rule_adherence=rule_adherence,
        anti_gaming_triggered=metric_gaming["triggered"],
    )
    overall, confidence_cap_events = _apply_confidence_caps(
        overall=overall,
        prompt_judge_method=str(pq_result.get("method") or "unknown"),
        calibration_samples=calibration_samples,
        run_accuracy_ci_half_width=run_accuracy_ci_half_width,
    )
    cap_events.extend(confidence_cap_events)
    return {
        "status": "ok",
        "overall": overall,
        "raw_overall": raw_overall,
        "metrics": {
            "accuracy": acc,
            "robustness": robustness,
            "reliability": rel,
            "efficiency": eff,
            "prompt_quality": pq,
            "orchestration": orch,
            "calibration": round(calibration, 4),
            "rule_adherence": rule_adherence,
        },
        "run_count": len(run_records),
        "tests_passed": sum(1 for r in run_records if r.get("status") == "pass"),
        "cap_events": cap_events,
        "anti_gaming_triggered": metric_gaming["triggered"],
        "usage": {
            "llm_calls": total_calls,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_prompt_tokens + total_completion_tokens,
            "cost_usd": round(total_cost, 6),
            "latency_ms": round(total_latency, 2),
        },
        "method": "sandbox_counterfactual_v1",
    }


def _counterfactual_strategy_variants(challenge_config: dict[str, Any]) -> list[dict[str, str]]:
    default_variants = [
        {
            "id": "strict_schema",
            "prompt": (
                "Follow schema exactly and return ONLY valid JSON with exact keys/types. "
                "Use null for unknowns, never prose, never markdown."
            ),
        },
        {
            "id": "normalize_and_extract",
            "prompt": (
                "Normalize dates/currency/names before extraction, then emit strict JSON only. "
                "Apply processing rules and avoid extra commentary."
            ),
        },
        {
            "id": "evidence_guardrail",
            "prompt": (
                "Verify every field against explicit input evidence before final output. "
                "If uncertain or unsupported, emit null rather than guessing."
            ),
        },
    ]
    requested = int(challenge_config.get("counterfactual_variants", 3) or 3)
    requested = max(1, min(3, requested))
    return default_variants[:requested]


def _build_counterfactual_baseline_code(
    challenge_config: dict[str, Any],
    challenge_description: str,
    *,
    strategy_prompt: str = "",
) -> str:
    template = _counterfactual_template_for_challenge(challenge_config)
    model_name = str(challenge_config.get("counterfactual_model", "gpt-4o-mini"))
    max_tokens = int(challenge_config.get("counterfactual_max_tokens", 1400))
    max_retries = max(1, min(3, int(challenge_config.get("counterfactual_retries", 2) or 2)))
    rules_preview = json.dumps(
        challenge_config.get("processing_rules", {}),
        ensure_ascii=False,
    )
    ground_truth = challenge_config.get("ground_truth", "")
    if isinstance(ground_truth, (dict, list)):
        schema_preview = json.dumps(ground_truth, ensure_ascii=False)
    else:
        schema_preview = str(ground_truth)
    if len(schema_preview) > 2400:
        schema_preview = schema_preview[:2400] + " ..."
    if len(rules_preview) > 1600:
        rules_preview = rules_preview[:1600] + " ..."
    description_preview = challenge_description.strip()
    if len(description_preview) > 1600:
        description_preview = description_preview[:1600] + " ..."

    return f"""import json
from pathlib import Path
from promptcode import llm

MODEL = {json.dumps(model_name)}
MAX_TOKENS = {max_tokens}
MAX_RETRIES = {max_retries}
DESCRIPTION = {json.dumps(description_preview)}
RULES = {json.dumps(rules_preview)}
SCHEMA = {json.dumps(schema_preview)}
TASK_FOCUS = {json.dumps(template["task_focus"])}
SYSTEM_PROMPT = {json.dumps(template["system_prompt"])}
STRATEGY_PROMPT = {json.dumps(strategy_prompt)}


def _load_input() -> str:
    p = Path("/workspace/input.json")
    if not p.exists():
        return ""
    return p.read_text()


def _to_valid_json(text: str) -> str:
    raw = (text or "").strip()
    try:
        json.loads(raw)
        return raw
    except json.JSONDecodeError:
        pass

    repair_prompt = (
        "Fix the following output into valid JSON matching the target schema.\\n\\n"
        + "Schema example:\\n" + SCHEMA + "\\n\\n"
        + "Broken output:\\n" + raw + "\\n\\n"
        + "Return ONLY valid JSON."
    )
    repaired = llm.call(
        model=MODEL,
        prompt=repair_prompt,
        system="You are a strict JSON repair assistant. Return ONLY valid JSON.",
        temperature=0,
        max_tokens=min(800, MAX_TOKENS),
        retries=1,
    )
    repaired = (repaired or "").strip()
    try:
        json.loads(repaired)
        return repaired
    except json.JSONDecodeError:
        return "{{}}"


raw_input = _load_input()
prompt = (
    "Solve the task using the input payload and return only valid JSON.\\n\\n"
    + "Strategy:\\n" + STRATEGY_PROMPT + "\\n\\n"
    + "Task focus:\\n" + TASK_FOCUS + "\\n\\n"
    + "Task:\\n" + DESCRIPTION + "\\n\\n"
    + "Normalization rules:\\n" + RULES + "\\n\\n"
    + "Expected output schema example:\\n" + SCHEMA + "\\n\\n"
    + "Input payload:\\n" + raw_input + "\\n\\n"
    + "Return ONLY JSON with no markdown."
)

response = llm.call(
    model=MODEL,
    prompt=prompt,
    system=SYSTEM_PROMPT,
    temperature=0,
    max_tokens=MAX_TOKENS,
    retries=MAX_RETRIES,
)
print(_to_valid_json(response))
"""


def _counterfactual_template_for_challenge(challenge_config: dict[str, Any]) -> dict[str, str]:
    slug = str(challenge_config.get("challenge_slug") or "").strip().lower()
    category = str(challenge_config.get("challenge_category") or "").strip().lower()

    by_slug: dict[str, dict[str, str]] = {
        "extract-structured-claims": {
            "task_focus": "Extract normalized insurance claim fields exactly and skip invalid/test records.",
            "system_prompt": "You are a strict insurance-claims extraction assistant. Output valid JSON only.",
        },
        "review-sentiment-synthesis": {
            "task_focus": "Synthesize review themes, sentiment, and prioritized product actions in structured JSON.",
            "system_prompt": "You are a customer-feedback analysis assistant. Output valid JSON only.",
        },
        "natural-language-to-sql": {
            "task_focus": "Map natural-language questions to correct SQL outputs using provided schema constraints.",
            "system_prompt": "You are a careful analytics assistant. Produce schema-constrained JSON only.",
        },
        "bug-report-dedup-triage": {
            "task_focus": "Cluster duplicate bugs and produce triage priority, owner routing, and root-cause hypotheses.",
            "system_prompt": "You are a software bug-triage assistant. Output valid JSON only.",
        },
        "email-thread-action-items": {
            "task_focus": "Extract actionable tasks, owners, deadlines, and risks from email threads.",
            "system_prompt": "You are an operations action-item extraction assistant. Output valid JSON only.",
        },
        "support-ticket-routing": {
            "task_focus": "Route support tickets to the right team with priority and concise reason.",
            "system_prompt": "You are a support triage assistant. Output valid JSON only.",
        },
        "resume-parsing-pipeline": {
            "task_focus": "Parse resumes into normalized structured candidate profiles with robust field handling.",
            "system_prompt": "You are a resume parsing assistant. Output valid JSON only.",
        },
        "contract-clause-extraction": {
            "task_focus": "Extract clause spans, classify clause types, and assign risk levels from legal contracts.",
            "system_prompt": "You are a legal clause extraction assistant. Output valid JSON only.",
        },
        "legacy-api-xml-to-json": {
            "task_focus": "Transform legacy XML responses into target JSON schema with strict normalization.",
            "system_prompt": "You are an enterprise data migration assistant. Output valid JSON only.",
        },
        "financial-anomaly-detection": {
            "task_focus": "Identify suspicious transactions and return categorized anomaly signals with evidence.",
            "system_prompt": "You are a financial anomaly detection assistant. Output valid JSON only.",
        },
    }
    if slug in by_slug:
        return by_slug[slug]

    by_category: dict[str, dict[str, str]] = {
        "extraction": {
            "task_focus": "Extract and normalize structured fields from noisy inputs.",
            "system_prompt": "You are a structured data extraction assistant. Output valid JSON only.",
        },
        "analysis": {
            "task_focus": "Analyze inputs and return concise structured findings.",
            "system_prompt": "You are an analysis assistant. Output valid JSON only.",
        },
    }
    if category in by_category:
        return by_category[category]
    return {
        "task_focus": "Follow task description exactly and return strict JSON output.",
        "system_prompt": "You are a strict structured output assistant. Output valid JSON only.",
    }
