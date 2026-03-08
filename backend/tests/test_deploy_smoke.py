from __future__ import annotations

import argparse

import pytest

from scripts import run_deploy_smoke


@pytest.fixture(autouse=True)
def clear_tls_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DOMAIN", raising=False)
    monkeypatch.delenv("HOST_IP", raising=False)
    monkeypatch.delenv("DEPLOY_HOST", raising=False)


def _args(**overrides) -> argparse.Namespace:
    data = {
        "base_url": "http://backend",
        "sandbox_executor_url": "http://sandbox-executor",
        "challenge_id": "",
        "email": "smoke@example.com",
        "password": "Password123!",
        "ready_timeout_seconds": 5,
        "timeout_seconds": 5,
        "poll_interval_seconds": 0.01,
        "domain": "",
        "host_ip": "",
        "tls_check": False,
        "code": "def solve(data):\n    return {}\n",
    }
    data.update(overrides)
    return argparse.Namespace(**data)


def test_smoke_exits_non_zero_when_sandbox_never_ready(monkeypatch: pytest.MonkeyPatch):
    calls = {"backend": 0, "sandbox": 0}

    def fake_wait(label: str, *_args, **_kwargs):
        if label == "backend":
            calls["backend"] += 1
            return {"status": "ok"}
        calls["sandbox"] += 1
        raise RuntimeError("sandbox-executor readiness failed: 503 {'status': 'error'}")

    monkeypatch.setattr(run_deploy_smoke, "_wait_for_ready", fake_wait)

    with pytest.raises(SystemExit) as exc_info:
        run_deploy_smoke.main([])

    assert "sandbox-executor readiness failed" in str(exc_info.value)
    assert calls == {"backend": 1, "sandbox": 1}


def test_smoke_exits_non_zero_when_no_challenges_seeded(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(run_deploy_smoke, "_wait_for_ready", lambda *_args, **_kwargs: {"status": "ok"})
    monkeypatch.setattr(run_deploy_smoke, "_signup_or_login", lambda *_args, **_kwargs: "token")
    monkeypatch.setattr(
        run_deploy_smoke,
        "_pick_challenge",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("Could not load challenges: 200 []")
        ),
    )

    with pytest.raises(SystemExit) as exc_info:
        run_deploy_smoke.main([])

    assert "Could not load challenges" in str(exc_info.value)


def test_smoke_exits_non_zero_when_submission_never_reaches_terminal_state(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(run_deploy_smoke, "_wait_for_ready", lambda *_args, **_kwargs: {"status": "ok"})
    monkeypatch.setattr(run_deploy_smoke, "_signup_or_login", lambda *_args, **_kwargs: "token")
    monkeypatch.setattr(run_deploy_smoke, "_pick_challenge", lambda *_args, **_kwargs: "challenge-1")
    monkeypatch.setattr(
        run_deploy_smoke,
        "_request",
        lambda *_args, **_kwargs: (201, {"id": "submission-1"}),
    )
    monkeypatch.setattr(
        run_deploy_smoke,
        "_poll_submission",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("Submission did not reach a terminal state: {'status': 'running'}")
        ),
    )

    with pytest.raises(SystemExit) as exc_info:
        run_deploy_smoke.main([])

    assert "Submission did not reach a terminal state" in str(exc_info.value)


@pytest.mark.parametrize("report_status", [404, 500])
def test_smoke_exits_non_zero_when_report_retrieval_fails(
    monkeypatch: pytest.MonkeyPatch,
    report_status: int,
):
    monkeypatch.setattr(run_deploy_smoke, "_wait_for_ready", lambda *_args, **_kwargs: {"status": "ok"})
    monkeypatch.setattr(run_deploy_smoke, "_signup_or_login", lambda *_args, **_kwargs: "token")
    monkeypatch.setattr(run_deploy_smoke, "_pick_challenge", lambda *_args, **_kwargs: "challenge-1")
    monkeypatch.setattr(run_deploy_smoke, "_poll_submission", lambda *_args, **_kwargs: {"status": "completed"})

    def fake_request(method: str, url: str, **_kwargs):
        if method == "POST":
            return 201, {"id": "submission-1"}
        if url.endswith("/report"):
            return report_status, {"detail": "missing"}
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr(run_deploy_smoke, "_request", fake_request)

    with pytest.raises(SystemExit) as exc_info:
        run_deploy_smoke.main([])

    assert "Completed submission report failed" in str(exc_info.value)


def test_smoke_runs_tls_checks_when_enabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(run_deploy_smoke, "_wait_for_ready", lambda *_args, **_kwargs: {"status": "ok"})
    monkeypatch.setattr(run_deploy_smoke, "_signup_or_login", lambda *_args, **_kwargs: "token")
    monkeypatch.setattr(run_deploy_smoke, "_pick_challenge", lambda *_args, **_kwargs: "challenge-1")
    monkeypatch.setattr(run_deploy_smoke, "_poll_submission", lambda *_args, **_kwargs: {"status": "completed"})

    def fake_request(method: str, url: str, **_kwargs):
        if method == "POST":
            return 201, {"id": "submission-1"}
        if url.endswith("/report"):
            return 200, {"id": "report-1"}
        raise AssertionError(f"Unexpected request: {method} {url}")

    tls_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(run_deploy_smoke, "_request", fake_request)
    monkeypatch.setattr(
        run_deploy_smoke,
        "_run_tls_checks",
        lambda domain, host_ip: tls_calls.append((domain, host_ip)) or {"host_ip_port_8000_refused": True},
    )

    result = run_deploy_smoke.run_smoke(
        _args(tls_check=True, domain="api.example.com", host_ip="203.0.113.10")
    )

    assert result["tls_checks"]["host_ip_port_8000_refused"] is True
    assert tls_calls == [("api.example.com", "203.0.113.10")]


def test_tls_checks_fail_when_http_does_not_redirect_to_https(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(run_deploy_smoke, "_request", lambda *_args, **_kwargs: (200, {"status": "ok"}))
    monkeypatch.setattr(
        run_deploy_smoke,
        "_request_without_redirects",
        lambda *_args, **_kwargs: (200, {}),
    )
    monkeypatch.setattr(run_deploy_smoke, "_assert_port_refused", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError) as exc_info:
        run_deploy_smoke._run_tls_checks("api.example.com", "203.0.113.10")

    assert "did not redirect to HTTPS" in str(exc_info.value)


def test_parse_args_enables_tls_checks_when_domain_and_host_ip_are_configured(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("DOMAIN", "api.example.com")
    monkeypatch.setenv("HOST_IP", "203.0.113.10")

    args = run_deploy_smoke.parse_args([])

    assert args.domain == "api.example.com"
    assert args.host_ip == "203.0.113.10"
    assert args.tls_check is True
