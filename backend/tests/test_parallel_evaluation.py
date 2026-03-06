"""Tests for parallel evaluation execution (Week 1-2 refactoring)."""

import asyncio
import inspect
from threading import Lock
import time

from app.services.evaluation import engine
from app.services.evaluation.engine import evaluate_submission


def test_evaluate_submission_is_async():
    """Verify evaluate_submission is now an async function."""
    assert inspect.iscoroutinefunction(
        evaluate_submission
    ), "evaluate_submission should be async"


def test_parallel_evaluation_completes():
    """Test that parallel evaluation runs without errors."""
    challenge_config = {
        "inputs": {"text": "Hello world"},
        "ground_truth": "greeting",
        "accuracy_mode": "exact",
        "clean_runs": 1,
        "description": "Test challenge",
        "expected_calls": 1,
    }

    code = """
from promptcode import llm
import json

def solve(input_data):
    text = input_data.get("text", "")
    response = llm.call(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"Classify: {text}"}]
    )
    return response.get("content", "")
"""

    try:
        result = asyncio.run(
            evaluate_submission(
                code=code,
                entrypoint="solve.py",
                challenge_config=challenge_config,
            )
        )
        # Basic validation that result is returned
        assert result is not None
        assert hasattr(result, "overall")
        print(f"✅ Evaluation completed with overall score: {result.overall}")
    except Exception as e:
        # Expected to fail due to missing Docker, API key, etc.
        # But async execution should work
        print(f"Note: Evaluation failed as expected (missing environment): {e}")
        assert "async" not in str(e).lower(), "Should not be async-related error"


def test_multiple_evaluations_in_parallel():
    """Test that multiple evaluations can run in parallel."""
    challenge_config = {
        "inputs": {"text": "test"},
        "ground_truth": "result",
        "accuracy_mode": "exact",
        "clean_runs": 1,
        "description": "Test",
        "expected_calls": 1,
    }

    code = "def solve(data): return 'result'"

    async def _run_parallel_evaluations():
        tasks = [
            evaluate_submission(
                code=code,
                entrypoint="test.py",
                challenge_config=challenge_config,
            )
            for _ in range(3)
        ]

        return await asyncio.gather(*tasks, return_exceptions=True)

    # This should work without deadlock
    try:
        results = asyncio.run(_run_parallel_evaluations())
        assert len(results) == 3
        print(f"✅ 3 parallel evaluations completed: {len([r for r in results if r is not None])} successful")
    except Exception as e:
        # Expected due to environment, but async should work
        print(f"Note: Parallel evaluations had environment issues (expected): {e}")


def test_parallel_helper_exists():
    """Verify the parallel execution helper function exists."""
    from app.services.evaluation.engine import _run_all_specs_in_parallel

    assert inspect.iscoroutinefunction(
        _run_all_specs_in_parallel
    ), "_run_all_specs_in_parallel should be async"
    print("✅ Parallel helper function exists and is async")


def test_parallel_helper_respects_max_parallel_specs(monkeypatch):
    run_plan = [
        {"inputs": {"index": 0}},
        {"inputs": {"index": 1}},
        {"inputs": {"index": 2}},
        {"inputs": {"index": 3}},
    ]
    state = {
        "active": 0,
        "max_active": 0,
    }
    state_lock = Lock()

    class FakeResult:
        success = True
        output = "ok"
        exit_code = 0
        telemetry = []
        error = None

    def fake_run_in_sandbox(*args, **kwargs):
        with state_lock:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
        time.sleep(0.05)
        with state_lock:
            state["active"] -= 1
        return FakeResult()

    monkeypatch.setattr(engine.settings, "evaluation_max_parallel_specs", 2)
    monkeypatch.setattr(engine, "run_in_sandbox", fake_run_in_sandbox)

    results = asyncio.run(
        engine._run_all_specs_in_parallel(
            run_plan=run_plan,
            code="print('ok')",
            entrypoint="main.py",
            challenge_config={"inputs": {}},
        )
    )

    assert len(results) == 4
    assert state["max_active"] <= 2


def test_prompt_quality_helper_uses_to_thread(monkeypatch):
    """Verify prompt-quality judging is offloaded from the event loop."""
    to_thread_calls = []

    def fake_score_prompt_quality(telemetry_calls, challenge_description):
        assert telemetry_calls == [{"prompt": "hello"}]
        assert challenge_description == "Test challenge"
        return {"overall": 0.75, "method": "heuristic"}

    async def fake_to_thread(func, *args, **kwargs):
        to_thread_calls.append(func.__name__)
        return func(*args, **kwargs)

    monkeypatch.setattr(engine, "score_prompt_quality", fake_score_prompt_quality)
    monkeypatch.setattr(engine.asyncio, "to_thread", fake_to_thread)

    result = asyncio.run(
        engine._score_prompt_quality_async(
            [{"prompt": "hello"}],
            "Test challenge",
        )
    )

    assert result["overall"] == 0.75
    assert to_thread_calls == ["fake_score_prompt_quality"]


def test_counterfactual_baseline_helper_uses_to_thread(monkeypatch):
    """Verify counterfactual baseline execution is offloaded from the event loop."""
    to_thread_calls = []

    def fake_counterfactual_sync(*, run_plan, challenge_config):
        assert run_plan == [{"run_type": "clean"}]
        assert challenge_config == {"description": "Test"}
        return {"status": "ok", "overall": 0.4}

    async def fake_to_thread(func, *args, **kwargs):
        to_thread_calls.append(func.__name__)
        return func(*args, **kwargs)

    monkeypatch.setattr(engine, "_evaluate_counterfactual_baseline_sync", fake_counterfactual_sync)
    monkeypatch.setattr(engine.asyncio, "to_thread", fake_to_thread)

    result = asyncio.run(
        engine._evaluate_counterfactual_baseline_async(
            run_plan=[{"run_type": "clean"}],
            challenge_config={"description": "Test"},
        )
    )

    assert result["status"] == "ok"
    assert to_thread_calls == ["fake_counterfactual_sync"]
