from __future__ import annotations

from types import SimpleNamespace

from app.services.evaluation.prompt_quality import _resolve_judge_models


def test_resolve_judge_models_prefers_primary_then_fallback():
    settings = SimpleNamespace(
        prompt_judge_model="gpt-4o-mini",
        prompt_judge_fallback_model="gpt-4o",
    )
    models = _resolve_judge_models(settings)
    assert models == ["gpt-4o-mini", "gpt-4o"]


def test_resolve_judge_models_defaults_when_empty():
    settings = SimpleNamespace(
        prompt_judge_model="",
        prompt_judge_fallback_model="",
    )
    models = _resolve_judge_models(settings)
    assert models == ["gpt-4o"]


def test_resolve_judge_models_filters_unsupported_and_keeps_supported():
    settings = SimpleNamespace(
        prompt_judge_model="anthropic/claude-opus-4.1,gpt-4o-mini",
        prompt_judge_fallback_model="claude-3-5-sonnet",
    )
    models = _resolve_judge_models(settings)
    assert models == ["gpt-4o-mini"]
