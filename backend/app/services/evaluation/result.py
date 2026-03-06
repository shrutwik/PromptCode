"""Evaluation result model."""

from __future__ import annotations

from typing import Any


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
        calibration: float,
        overall: float,
        cost_usd: float,
        latency_ms: float,
        llm_calls: int,
        prompt_tokens: int,
        completion_tokens: int,
        retries: int,
        runs: list[dict[str, Any]],
        prompt_quality_details: dict[str, Any],
        code_analysis_details: dict[str, Any],
        calibration_details: dict[str, Any],
        diagnostics: list[dict[str, str]],
        evaluation_config: dict[str, Any],
        ai_leverage: dict[str, Any] | None = None,
        usage_breakdown: dict[str, Any] | None = None,
        credibility: dict[str, Any] | None = None,
        confidence_intervals: dict[str, Any] | None = None,
        audit_trail: list[dict[str, Any]] | None = None,
        evaluation_manifest: dict[str, Any] | None = None,
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
        self.calibration = calibration
        self.overall = overall
        self.cost_usd = cost_usd
        self.latency_ms = latency_ms
        self.llm_calls = llm_calls
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.retries = retries
        self.runs = runs
        self.prompt_quality_details = prompt_quality_details
        self.code_analysis_details = code_analysis_details
        self.calibration_details = calibration_details
        self.diagnostics = diagnostics
        self.evaluation_config = evaluation_config
        self.ai_leverage = ai_leverage or {}
        self.usage_breakdown = usage_breakdown or {}
        self.credibility = credibility or {}
        self.confidence_intervals = confidence_intervals or {}
        self.audit_trail = audit_trail or []
        self.evaluation_manifest = evaluation_manifest or {}
        self.hardcoded = hardcoded

    def to_report(self, submission_id: str) -> dict[str, Any]:
        tests_passed = sum(1 for r in self.runs if r.get("status") == "pass")
        tests_total = len(self.runs)
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
            "calibration": self.calibration,
            "overall": self.overall,
            "cost_usd": round(self.cost_usd, 6),
            "latency_ms": round(self.latency_ms, 2),
            "llm_calls": self.llm_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
            "retries": self.retries,
            "tests_passed": tests_passed,
            "tests_total": tests_total,
            "runs": self.runs,
            "prompt_quality_details": self.prompt_quality_details,
            "code_analysis_details": self.code_analysis_details,
            "calibration_details": self.calibration_details,
            "diagnostics": self.diagnostics,
            "feedback": self.diagnostics[0]["message"] if self.diagnostics else "",
            "evaluation_config": self.evaluation_config,
            "ai_leverage": self.ai_leverage,
            "usage_breakdown": self.usage_breakdown,
            "credibility": self.credibility,
            "confidence_intervals": self.confidence_intervals,
            "audit_trail": self.audit_trail,
            "evaluation_manifest": self.evaluation_manifest,
            "scorecard": {
                "accuracy": self.accuracy,
                "robustness": self.edge_case_handling,
                "reliability": self.reliability,
                "efficiency": self.efficiency,
                "prompt_design": self.prompt_quality,
                "orchestration": self.orchestration,
                "calibration": self.calibration,
                "ai_mastery": float(self.ai_leverage.get("ai_mastery_score", 0.0)),
            },
        }
        if self.hardcoded:
            report["disqualified"] = True
            report["disqualification_reason"] = (
                "Submission appears to contain hardcoded answers rather than "
                "using AI to solve the problem. All scores have been zeroed."
            )
        return report
