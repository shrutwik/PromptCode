from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import app.models  # noqa: F401
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models.challenge import Challenge
from app.models.evaluation_job import EvaluationJob
from app.services.evaluation.engine import EvaluationResult
from app.workers import evaluate as evaluate_worker
from app.workers import queue as queue_worker


def _fake_result() -> EvaluationResult:
    runs = [
        {
            "run_type": "clean",
            "run_index": 0,
            "status": "pass",
            "accuracy": 0.95,
            "schema_valid": True,
            "confidence": 0.92,
            "tokens_prompt": 20,
            "tokens_completion": 10,
            "tokens_total": 30,
            "cost_usd": 0.001,
            "latency_ms": 25.0,
            "llm_calls": 1,
            "retries": 0,
            "meta": {"seed": 1},
        },
        {
            "run_type": "clean",
            "run_index": 1,
            "status": "pass",
            "accuracy": 0.94,
            "schema_valid": True,
            "confidence": 0.91,
            "tokens_prompt": 18,
            "tokens_completion": 11,
            "tokens_total": 29,
            "cost_usd": 0.001,
            "latency_ms": 24.0,
            "llm_calls": 1,
            "retries": 0,
            "meta": {"seed": 2},
        },
        {
            "run_type": "perturbed",
            "run_index": 0,
            "status": "pass",
            "accuracy": 0.88,
            "schema_valid": True,
            "confidence": 0.86,
            "tokens_prompt": 22,
            "tokens_completion": 10,
            "tokens_total": 32,
            "cost_usd": 0.0012,
            "latency_ms": 28.0,
            "llm_calls": 1,
            "retries": 0,
            "meta": {"seed": 3},
        },
        {
            "run_type": "perturbed",
            "run_index": 1,
            "status": "pass",
            "accuracy": 0.87,
            "schema_valid": True,
            "confidence": 0.85,
            "tokens_prompt": 21,
            "tokens_completion": 10,
            "tokens_total": 31,
            "cost_usd": 0.0011,
            "latency_ms": 27.0,
            "llm_calls": 1,
            "retries": 0,
            "meta": {"seed": 4},
        },
        {
            "run_type": "adversarial",
            "run_index": 0,
            "status": "pass",
            "accuracy": 0.83,
            "schema_valid": True,
            "confidence": 0.8,
            "tokens_prompt": 24,
            "tokens_completion": 12,
            "tokens_total": 36,
            "cost_usd": 0.0014,
            "latency_ms": 30.0,
            "llm_calls": 1,
            "retries": 0,
            "meta": {"seed": 5},
        },
        {
            "run_type": "adversarial",
            "run_index": 1,
            "status": "pass",
            "accuracy": 0.82,
            "schema_valid": True,
            "confidence": 0.79,
            "tokens_prompt": 23,
            "tokens_completion": 12,
            "tokens_total": 35,
            "cost_usd": 0.0013,
            "latency_ms": 29.0,
            "llm_calls": 1,
            "retries": 0,
            "meta": {"seed": 6},
        },
    ]
    return EvaluationResult(
        accuracy=0.945,
        prompt_quality=0.86,
        rule_adherence=0.94,
        efficiency=0.81,
        reliability=0.9,
        orchestration=0.84,
        code_quality=0.88,
        edge_case_handling=0.85,
        calibration=0.79,
        overall=0.875,
        cost_usd=0.007,
        latency_ms=163.0,
        llm_calls=6,
        prompt_tokens=128,
        completion_tokens=65,
        retries=0,
        runs=runs,
        prompt_quality_details={
            "clarity": 0.86,
            "specificity": 0.85,
            "structure": 0.87,
            "efficiency": 0.83,
            "robustness": 0.84,
            "grounding": 0.89,
            "overall": 0.86,
            "feedback": "Strong structured prompting.",
            "method": "llm_judge",
        },
        code_analysis_details={
            "score": 0.88,
            "analysis": {"has_validation": True},
            "penalties": [],
        },
        calibration_details={"score": 0.79, "samples": 6},
        diagnostics=[
            {
                "metric": "summary",
                "severity": "low",
                "message": "Balanced submission: no critical weaknesses detected in this run set.",
            }
        ],
        evaluation_config={"run_count": 6},
        ai_leverage={
            "frontier_navigation_score": 0.82,
            "reliance_calibration_score": 0.8,
            "learning_velocity_score": 0.5,
            "counterfactual_baseline_overall": 0.73,
            "leverage_gain": 0.145,
            "leverage_gain_score": 0.61,
            "ai_mastery_score": 0.81,
            "signals": {
                "counterfactual": {"status": "ok"},
            },
            "method": "counterfactual_v1",
        },
        usage_breakdown={
            "totals": {
                "calls": 6,
                "retries": 0,
                "prompt_tokens": 128,
                "completion_tokens": 65,
                "total_tokens": 193,
                "cost_usd": 0.007,
                "latency_ms": 163.0,
            },
            "models": [{"model": "gpt-4o-mini", "calls": 6}],
            "run_types": [{"run_type": "clean", "runs": 2, "passes": 2, "pass_rate": 1.0}],
            "method": "telemetry_aggregation_v1",
        },
        credibility={"score": 0.92, "band": "high", "method": "credibility_v1"},
        confidence_intervals={"accuracy": {"mean": 0.945}},
        audit_trail=[{"event": "evaluation_completed"}],
        evaluation_manifest={"version": 1, "replay_hash": "abc123"},
        hardcoded=False,
    )


async def _seed_challenge(session_factory: async_sessionmaker) -> uuid.UUID:
    async with session_factory() as session:
        challenge = Challenge(
            slug="integration-flow",
            title="Integration Flow",
            description="Return a JSON payload.",
            category="extraction",
            config={
                "inputs": {"text": "hello"},
                "ground_truth": {"value": "ok"},
                "accuracy_mode": "json",
                "expected_calls": 1,
            },
            sample_input={"text": "hello"},
            sample_output={"value": "ok"},
        )
        session.add(challenge)
        await session.commit()
        await session.refresh(challenge)
        return challenge.id


async def _find_job_id(
    session_factory: async_sessionmaker,
    submission_id: str,
) -> str:
    async with session_factory() as session:
        result = await session.execute(
            select(EvaluationJob).where(EvaluationJob.submission_id == uuid.UUID(submission_id))
        )
        job = result.scalar_one()
        return str(job.id)


def test_signup_submit_evaluate_and_fetch_report_flow(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "integration-flow.db"
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def create_schema() -> None:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())

    async def override_get_db():
        async with session_factory() as session:
            yield session

    from app import main as main_module
    from app.db import session as session_module

    monkeypatch.setattr(session_module, "engine", test_engine)
    monkeypatch.setattr(session_module, "async_session_factory", session_factory)
    monkeypatch.setattr(main_module, "engine", test_engine)
    monkeypatch.setattr(queue_worker, "async_session_factory", session_factory)
    monkeypatch.setattr(evaluate_worker, "async_session_factory", session_factory)

    async def fake_evaluate_submission(*args, **kwargs):
        return _fake_result()

    monkeypatch.setattr(evaluate_worker, "evaluate_submission", fake_evaluate_submission)

    challenge_id = asyncio.run(_seed_challenge(session_factory))

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        signup = client.post(
            "/api/auth/signup",
            json={
                "email": "flow@example.com",
                "username": "flow_user",
                "first_name": "Flow",
                "last_name": "User",
                "password": "Password123!",
            },
        )
        assert signup.status_code == 201
        token = signup.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        submission = client.post(
            "/api/submissions/",
            json={
                "challenge_id": str(challenge_id),
                "code": "def solve(data): return {'value': 'ok'}",
                "entrypoint": "main.py",
            },
            headers=headers,
        )
        assert submission.status_code == 201
        submission_id = submission.json()["id"]

        job_id = asyncio.run(_find_job_id(session_factory, submission_id))
        asyncio.run(queue_worker.process_job(job_id))

        status = client.get(f"/api/submissions/{submission_id}/status", headers=headers)
        assert status.status_code == 200
        assert status.json()["status"] == "completed"
        assert status.json()["score_overall"] == 0.875

        report = client.get(f"/api/submissions/{submission_id}/report", headers=headers)
        assert report.status_code == 200
        report_json = report.json()
        assert report_json["overall"] == 0.875
        assert report_json["ai_leverage"]["signals"]["counterfactual"]["status"] == "ok"
        assert report_json["future_feedback"]["readiness_band"] in {"medium", "high"}

        leaderboard = client.get(f"/api/leaderboard/{challenge_id}?limit=5")
        assert leaderboard.status_code == 200
        entries = leaderboard.json()
        assert len(entries) == 1
        assert entries[0]["username"] == "flow_user"
        assert entries[0]["score_overall"] == 0.875

    app.dependency_overrides.clear()
    asyncio.run(test_engine.dispose())
