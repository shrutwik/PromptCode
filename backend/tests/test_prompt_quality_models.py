from __future__ import annotations

import json
from types import SimpleNamespace

from app.core import config as config_module
from app.services.evaluation import prompt_quality
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


def test_resolve_judge_models_normalizes_provider_prefixed_models():
    settings = SimpleNamespace(
        prompt_judge_model="protected.gpt-4o-mini,openai:gpt-4o",
        prompt_judge_fallback_model="openai/gpt-4o",
    )
    models = _resolve_judge_models(settings)
    assert models == ["protected.gpt-4o-mini", "openai:gpt-4o"]


def test_resolve_judge_models_defaults_to_openai_model_when_supported():
    settings = SimpleNamespace(
        prompt_judge_model="",
        prompt_judge_fallback_model="",
        openai_model="protected.gpt-4o",
    )
    models = _resolve_judge_models(settings)
    assert models == ["protected.gpt-4o"]


def test_resolve_judge_models_appends_provider_default_alias_for_same_canonical_model():
    settings = SimpleNamespace(
        prompt_judge_model="gpt-4o",
        prompt_judge_fallback_model="",
        openai_model="protected.gpt-4o",
    )
    models = _resolve_judge_models(settings)
    assert models == ["gpt-4o", "protected.gpt-4o"]


def test_score_prompt_quality_accepts_string_judge_response(monkeypatch):
    settings = SimpleNamespace(
        openai_api_key="sk-test",
        openai_base_url="",
        prompt_judge_model="gpt-4o",
        prompt_judge_fallback_model="",
        openai_model="gpt-4o",
    )

    class _FakeCompletions:
        def create(self, **kwargs):
            return json.dumps(
                {
                    "clarity": 0.8,
                    "specificity": 0.9,
                    "structure": 0.7,
                    "efficiency": 0.75,
                    "robustness": 0.85,
                    "grounding": 0.6,
                    "overall": 0.81,
                    "feedback": "Solid prompt structure.",
                }
            )

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    monkeypatch.setattr(config_module, "get_settings", lambda: settings)
    monkeypatch.setattr(prompt_quality.openai, "OpenAI", lambda **kwargs: _FakeClient())

    result = prompt_quality.score_prompt_quality(
        [
            {
                "prompt": "Return valid JSON",
                "system": "You are a parser",
                "model": "gpt-4o",
            }
        ],
        "Extract fields",
    )

    assert result["method"] == "llm_judge"
    assert result["judge_model"] == "gpt-4o"
    assert result["overall"] == 0.81


def test_score_prompt_quality_accepts_event_stream_string_response(monkeypatch):
    settings = SimpleNamespace(
        openai_api_key="sk-test",
        openai_base_url="",
        prompt_judge_model="gpt-4o",
        prompt_judge_fallback_model="",
        openai_model="protected.gpt-4o",
    )
    event_stream = (
        'data: {"choices":[{"delta":{"content":"{\\"clarity\\":"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"0.8,\\"specificity\\":0.9,\\"structure\\":0.7,\\"efficiency\\":0.75,\\"robustness\\":0.85,\\"grounding\\":0.6,\\"overall\\":0.81,\\"feedback\\":\\"Solid prompt structure.\\"}"}}]}\n\n'
        'data: [DONE]\n\n'
    )

    class _FakeCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise prompt_quality.openai.BadRequestError(
                    message="Model not found",
                    response=SimpleNamespace(status_code=400, request=None, text='{"detail":"Model not found"}'),
                    body={"detail": "Model not found"},
                )
            return event_stream

    fake_completions = _FakeCompletions()

    class _FakeChat:
        completions = fake_completions

    class _FakeClient:
        chat = _FakeChat()

    monkeypatch.setattr(config_module, "get_settings", lambda: settings)
    monkeypatch.setattr(prompt_quality.openai, "OpenAI", lambda **kwargs: _FakeClient())

    result = prompt_quality.score_prompt_quality(
        [
            {
                "prompt": "Return valid JSON",
                "system": "You are a parser",
                "model": "gpt-4o",
            }
        ],
        "Extract fields",
    )

    assert result["method"] == "llm_judge"
    assert result["judge_model"] == "protected.gpt-4o"
    assert result["overall"] == 0.81
