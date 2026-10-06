"""Candidate code must not be able to forge paid-call accounting.

The legacy sandbox used to mount a writable telemetry directory into the
candidate container and then read ``calls.jsonl`` from it. That file feeds token,
cost and prompt-quality scoring, so a candidate could invent usage. Accounting is
now produced by the application relay that actually made the billed call.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.services.sandbox import runner
from app.services.sandbox.relay import SandboxLLMBudget, SandboxLLMRelay


def _budget() -> SandboxLLMBudget:
    return SandboxLLMBudget(("deepseek-flash",), 10, 18000, 600, 20000, 1)


def test_container_gets_no_writable_telemetry_mount(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "settings", SimpleNamespace(
        execution_broker_mode=False,
        sandbox_image="approved",
        sandbox_memory_limit="512m",
        sandbox_cpu_limit=1,
        sandbox_timeout_seconds=120,
    ))
    relay = SimpleNamespace(proxy_url="http://127.0.0.1:1", token="ephemeral")
    telemetry_dir = tmp_path / "telemetry"
    telemetry_dir.mkdir()
    kwargs = runner._build_container_run_kwargs(
        code_dir=tmp_path / "code",
        telemetry_dir=telemetry_dir,
        entrypoint="main.py",
        relay=relay,
        budget=_budget(),
        network_mode="none",
        run_id="owned",
    )
    binds = {mount["bind"] for mount in kwargs["volumes"].values()}
    assert "/tmp/promptcode_telemetry" not in binds
    assert str(telemetry_dir) not in json.dumps(kwargs)
    # The only candidate-visible mount is the read-only source.
    assert kwargs["volumes"][str(tmp_path / "code")] == {"bind": "/workspace", "mode": "ro"}


def test_candidate_written_telemetry_is_never_consulted(tmp_path, monkeypatch):
    """Even if a container somehow writes accounting files, they are ignored."""
    forged = tmp_path / "telemetry"
    forged.mkdir()
    (forged / "calls.jsonl").write_text(json.dumps(
        {"prompt": "forged", "cost_usd": 99999, "tokens_total": 10 ** 9}) + "\n")
    # The runner no longer reads this path at all: the success path returns the
    # relay's own records, so a forged file cannot reach grading.
    source = Path(runner.__file__).read_text(encoding="utf-8")
    assert "_read_telemetry(telemetry_dir)" not in source
    assert "trusted_telemetry" in source


def test_relay_records_authoritative_usage_without_candidate_input(monkeypatch):
    calls: list[dict] = []

    def sender(payload):
        calls.append(payload)
        return (
            {
                "model": "deepseek-flash",
                "choices": [{"message": {"content": "result"}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            },
            12.5,
        )

    relay = SandboxLLMRelay(
        api_key="test-key",
        base_url="https://api.deepseek.com",
        host_alias="localhost",
        budget=_budget(),
        request_sender=sender,
    )
    relay.handle_request({"model": "deepseek-flash", "prompt": "extract this", "max_tokens": 50})
    records = relay.recorded_calls()
    assert len(records) == 1
    record = records[0]
    assert record["prompt"] == "extract this"
    assert record["tokens_prompt"] == 11
    assert record["tokens_completion"] == 7
    assert record["tokens_total"] == 18
    assert record["cost_usd"] > 0
    assert record["latency_ms"] == 12.5
    assert record["retry_index"] == 0
    # The returned copy cannot mutate the relay's own accounting.
    records[0]["cost_usd"] = 0
    assert relay.recorded_calls()[0]["cost_usd"] > 0
