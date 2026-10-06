"""Safety and measurement checks for the bounded capacity workload."""
import json
import time
from argparse import Namespace

import pytest
from benchmarks.interview_load import Measurements, load_accounts, parse_args, user_flow


def test_accounts_require_unique_explicit_disposable_namespace(tmp_path):
    path = tmp_path / "accounts.json"
    payload = {"namespace": "pilot", "disposable": True, "accounts": [
        {"email": "benchmark_pilot_1@example.com", "access_token": "secret"}]}
    path.write_text(json.dumps(payload))
    assert len(load_accounts(path, "pilot", 1)) == 1
    for mutation in ({"disposable": False}, {"namespace": "other"}, {"accounts": payload["accounts"] * 2},
                     {"accounts": [{"email": "real@example.com", "access_token": "secret"}]}):
        path.write_text(json.dumps({**payload, **mutation}))
        with pytest.raises(ValueError):
            load_accounts(path, "pilot", 1)


@pytest.mark.parametrize("extra", [
    ["--base-url", "http://remote.example"], ["--base-url", "https://user:pass@example.com"],
    ["--stages", "100", "50"], ["--stages", "101"], ["--stage-timeout", "0"],
    ["--max-error-rate", "nan"], ["--poll-interval", "0"],
    ["--base-url", "https://remote.example", "--local-host-telemetry"],
])
def test_cli_rejects_unsafe_or_unbounded_arguments(extra):
    with pytest.raises(SystemExit):
        parse_args(["--base-url", "http://127.0.0.1:8000", "--accounts", "accounts.json",
                    "--namespace", "pilot", "--output", "report.json", *extra])


def test_throttles_are_reported_separately_and_stop_excessive_load():
    measurements = Measurements(max_error_rate=0.1, max_throttle_rate=0.25)
    for _ in range(19):
        measurements.record("run", 429, 10, True)
    assert not measurements.stop.is_set()
    measurements.record("run", 503, 20, True)
    result = measurements.summary()
    assert result["unexpected_errors"] == 0
    assert result["throttles"] == 20
    assert result["stop_threshold_reached"]
    assert result["steps"]["run"]["latency_ms"]["p95"] == 10
    assert result["steps"]["run"]["successful_latency_ms"]["samples"] == 0


def test_identity_is_verified_before_any_session_mutation(monkeypatch):
    calls = []
    def fake_call(self, step, method, path, payload=None):
        calls.append(step)
        return {"email": "real@example.com"}
    monkeypatch.setattr("benchmarks.interview_load.Client.call", fake_call)
    args = Namespace(base_url="http://127.0.0.1:8000", request_timeout=10)
    measurements = Measurements(0.1, 0.25)
    assert user_flow({"email": "benchmark_pilot_1@example.com", "access_token": "secret"},
                     args, measurements, time.monotonic() + 30) is None
    assert calls == ["identity"]
    assert measurements.summary()["flow_failures"] == {"account_identity_mismatch": 1}
    assert "secret" not in json.dumps(measurements.summary())


def test_candidate_test_failure_is_not_an_infrastructure_failure(monkeypatch):
    def fake_call(self, step, method, path, payload=None):
        responses = {
            "identity": {"email": "benchmark_pilot_1@example.com"}, "challenge": {},
            "start": {"id": "sid", "owner_token": "secret"}, "files": [{"path": "main.py"}],
            "read": {"content": "x = 1"}, "save": {},
            "advisory_run": {"ok": False, "exit_code": 1, "duration_ms": 10},
            "submit": {"defend_questions": []}, "defend": {},
            "report": {"assessment": {"execution_status": "completed"}}, "dashboard": {},
        }
        return responses[step]
    monkeypatch.setattr("benchmarks.interview_load.Client.call", fake_call)
    args = Namespace(base_url="http://127.0.0.1:8000", request_timeout=10, challenge="test",
                     skip_execution=False, poll_interval=0.1, capacity_retries=0)
    measurements = Measurements(0.1, 0.25)
    user_flow({"email": "benchmark_pilot_1@example.com", "access_token": "secret"}, args,
              measurements, time.monotonic() + 30)
    assert measurements.summary()["flows"] == {"completed": 1}
    assert measurements.summary()["advisory_execution_duration_ms"]["samples"] == 1


def test_local_entry_excludes_saved_configuration_credentials(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path

    from benchmarks.run_local_capacity import isolated_module

    saved_config = tmp_path / "saved.env"
    saved_config.write_text("PROMPTCODE_SENTRY_DSN=DO_NOT_IMPORT_SAVED_CREDENTIAL\n")
    (tmp_path / "capacity_config_probe.py").write_text(
        "import json\nfrom app.core.config import get_settings\n"
        "print(json.dumps({'saved_credential': get_settings().sentry_dsn}))\n"
    )
    env = {"PATH": os.environ.get("PATH", ""), "PROMPTCODE_DEBUG": "true",
           "PROMPTCODE_JWT_SECRET": "capacity-test-secret", "PROMPTCODE_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
           "PYTHONPATH": os.pathsep.join((str(Path(__file__).resolve().parents[1]), str(tmp_path)))}
    controlled_source = ("from app.core.config import Settings; Settings.model_config['env_file'] = "
                         + repr(str(saved_config)) + "; ")
    control = subprocess.run([sys.executable, "-c", controlled_source + "import capacity_config_probe"],
                             env=env, capture_output=True, text=True, timeout=10, check=True)
    assert json.loads(control.stdout)["saved_credential"] == "DO_NOT_IMPORT_SAVED_CREDENTIAL"
    arguments = isolated_module("capacity_config_probe")
    arguments[2] = controlled_source + arguments[2]
    isolated = subprocess.run(arguments, env=env, capture_output=True, text=True, timeout=10, check=True)
    assert json.loads(isolated.stdout)["saved_credential"] == ""
