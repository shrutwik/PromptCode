"""Grading probe sweeps run bounded-parallel inside one admitted slot.

The sweep used to run each case sequentially, so a 3-7 case inventory at up to
12 s per case occupied an execution slot for 36-84 s — the dominant contributor
to grading-queue latency. Cases are independent read-only probes over the same
frozen source, so they can run concurrently up to a configured bound. These tests
prove the bound is respected and that results still map to inventory order, which
the trusted evaluator cross-checks position by position.
"""
from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest

from app import execution_broker as broker


class _Case:
    def __init__(self, case_id: str, probe: str) -> None:
        self.id = case_id
        self.probe = probe


@pytest.fixture
def parallel_settings(monkeypatch):
    settings = SimpleNamespace(probe_concurrency=2)
    monkeypatch.setattr(broker, "get_settings", lambda: settings)
    return settings


def test_sweep_runs_cases_concurrently_within_the_bound(monkeypatch, parallel_settings):
    cases = [_Case(f"case-{i}", f"probe-{i}") for i in range(4)]
    monkeypatch.setattr(broker, "cases_for", lambda _slug: cases)

    lock = threading.Lock()
    active = 0
    peak = 0

    def fake_probe(source, slug, probe, image=None):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return f"observed:{probe}", None

    monkeypatch.setattr(broker, "_run_probe", fake_probe)
    observations = broker._run_probe_sweep("source", "slug", "image")

    assert [item["id"] for item in observations] == [case.id for case in cases]
    assert [item["observed"] for item in observations] == [f"observed:probe-{i}" for i in range(4)]
    assert peak == 2, f"expected the configured bound of 2 concurrent probes, saw {peak}"


def test_single_case_inventory_does_not_spawn_a_pool(monkeypatch, parallel_settings):
    monkeypatch.setattr(broker, "cases_for", lambda _slug: [_Case("only", "probe")])
    calls: list[str] = []
    monkeypatch.setattr(broker, "_run_probe",
                        lambda source, slug, probe, image=None: (calls.append(probe), ("v", None))[1])
    observations = broker._run_probe_sweep("source", "slug", "image")
    assert observations == [{"id": "only", "observed": "v", "error": None}]
    assert calls == ["probe"]


def test_probe_errors_are_attributed_to_their_case(monkeypatch, parallel_settings):
    cases = [_Case("ok", "a"), _Case("bad", "b"), _Case("timeout", "c")]
    monkeypatch.setattr(broker, "cases_for", lambda _slug: cases)

    def fake_probe(source, slug, probe, image=None):
        if probe == "b":
            return None, "candidate_error"
        if probe == "c":
            return None, "timeout"
        return 42, None

    monkeypatch.setattr(broker, "_run_probe", fake_probe)
    observations = broker._run_probe_sweep("source", "slug", "image")
    assert observations == [
        {"id": "ok", "observed": 42, "error": None},
        {"id": "bad", "observed": None, "error": "candidate_error"},
        {"id": "timeout", "observed": None, "error": "timeout"},
    ]


def test_empty_inventory_returns_no_observations(monkeypatch, parallel_settings):
    monkeypatch.setattr(broker, "cases_for", lambda _slug: [])
    assert broker._run_probe_sweep("source", "slug", "image") == []


def test_probe_concurrency_is_bounded_by_configuration():
    from pydantic import ValidationError

    from app.core.config import Settings

    assert Settings.model_fields["probe_concurrency"].default == 2
    with pytest.raises(ValidationError):
        Settings(probe_concurrency=0)
    with pytest.raises(ValidationError):
        Settings(probe_concurrency=9)
