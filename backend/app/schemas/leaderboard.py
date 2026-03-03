from __future__ import annotations

import uuid

from pydantic import BaseModel


class LeaderboardEntryResponse(BaseModel):
    rank: int | None
    user_id: uuid.UUID
    username: str = ""
    submission_id: uuid.UUID
    score_overall: float
    score_accuracy: float
    score_prompt_quality: float
    score_efficiency: float
    score_reliability: float
    score_orchestration: float
    score_code_quality: float
    score_rule_adherence: float = 0.0
    score_edge_cases: float = 0.0
    total_cost_usd: float
    total_llm_calls: int

    model_config = {"from_attributes": True}
