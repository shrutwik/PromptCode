from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SubmissionCreate(BaseModel):
    challenge_id: uuid.UUID
    code: str
    entrypoint: str = "main.py"


class SubmissionResponse(BaseModel):
    id: uuid.UUID
    challenge_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    entrypoint: str
    score_accuracy: float | None = None
    score_prompt_quality: float | None = None
    score_efficiency: float | None = None
    score_reliability: float | None = None
    score_orchestration: float | None = None
    score_code_quality: float | None = None
    score_rule_adherence: float | None = None
    score_edge_cases: float | None = None
    score_overall: float | None = None
    total_cost_usd: float | None = None
    total_latency_ms: float | None = None
    total_llm_calls: int | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class PromptQualityBreakdown(BaseModel):
    clarity: float
    specificity: float
    structure: float
    efficiency: float
    robustness: float
    grounding: float
    overall: float
    feedback: str
    method: str


class CodeQualityBreakdown(BaseModel):
    score: float
    analysis: dict[str, Any]
    penalties: list[str]


class SubmissionReport(BaseModel):
    """The Prompt Efficiency Report returned to the user."""

    submission_id: uuid.UUID
    accuracy: float
    prompt_quality: float
    rule_adherence: float = 0.0
    efficiency: float
    reliability: float
    orchestration: float
    code_quality: float
    edge_case_handling: float = 0.0
    calibration: float = 0.5
    overall: float
    cost_usd: float
    latency_ms: float
    llm_calls: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    retries: int | None = None
    tests_passed: int | None = None
    tests_total: int | None = None
    prompt_quality_details: PromptQualityBreakdown | dict[str, Any] = {}
    code_analysis_details: CodeQualityBreakdown | dict[str, Any] = {}
    calibration_details: dict[str, Any] = {}
    diagnostics: list[dict[str, Any]] = []
    feedback: str = ""
    scorecard: dict[str, float] = {}
    evaluation_config: dict[str, Any] = {}
    evaluation_manifest: dict[str, Any] = {}
    confidence_intervals: dict[str, Any] = {}
    audit_trail: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
