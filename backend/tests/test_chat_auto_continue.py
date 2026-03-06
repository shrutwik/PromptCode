from __future__ import annotations

import asyncio

from app.api.routes.chat import _run_completion_with_auto_continue


def _payload(*, content: str, finish_reason: str, model: str = "gpt-4o") -> dict:
    return {
        "id": f"resp-{content}",
        "model": model,
        "choices": [
            {
                "message": {"content": content},
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }


def test_auto_continue_appends_notice_only_when_requested():
    responses = [
        _payload(content="part1", finish_reason="length"),
        _payload(content="part2", finish_reason="length"),
        _payload(content="part3", finish_reason="length"),
        _payload(content="part4", finish_reason="length"),
    ]
    index = {"value": 0}

    async def request_completion(_messages):
        response = responses[index["value"]]
        index["value"] += 1
        return response, 25.0

    reply, model_name, usage, latency_ms, raw_id = asyncio.run(
        _run_completion_with_auto_continue(
            base_messages=[{"role": "user", "content": "hello"}],
            model="gpt-4o",
            request_completion=request_completion,
            truncation_notice='[Output may still be truncated. Ask "continue" for more.]',
        )
    )

    assert reply.endswith('[Output may still be truncated. Ask "continue" for more.]')
    assert "part1part2part3part4" in reply
    assert model_name == "gpt-4o"
    assert usage["total_tokens"] == 60
    assert latency_ms == 100.0
    assert raw_id == "resp-part4"


def test_auto_continue_keeps_structured_output_clean_without_notice():
    responses = [
        _payload(content='{"items":[', finish_reason="length", model="gpt-4-turbo"),
        _payload(content='1,2,3', finish_reason="length", model="gpt-4-turbo"),
        _payload(content=']}', finish_reason="stop", model="gpt-4-turbo"),
    ]
    index = {"value": 0}

    async def request_completion(_messages):
        response = responses[index["value"]]
        index["value"] += 1
        return response, 10.0

    reply, model_name, usage, latency_ms, raw_id = asyncio.run(
        _run_completion_with_auto_continue(
            base_messages=[{"role": "user", "content": "return json"}],
            model="gpt-4-turbo",
            request_completion=request_completion,
        )
    )

    assert reply == '{"items":[1,2,3]}'
    assert model_name == "gpt-4-turbo"
    assert usage["total_tokens"] == 45
    assert latency_ms == 30.0
    assert raw_id == "resp-]}"
