"""The alert transport is the only way an operational failure reaches a human.

There is no alert manager in the deployment, so these tests pin the delivery
contract and, importantly, that a missing destination stays a no-op: a health
check must never fail merely because alerting is not configured yet.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NOTIFY = REPO_ROOT / "scripts" / "notify-alert.sh"


def _run(env: dict[str, str], *args: str) -> subprocess.CompletedProcess:
    import os

    base = os.environ.copy()
    base.pop("PROMPTCODE_ALERT_WEBHOOK_URL", None)
    base.pop("PROMPTCODE_ALERT_COMMAND", None)
    base.update(env)
    return subprocess.run(["bash", str(NOTIFY), *args], capture_output=True, text=True,
                          check=False, env=base)


def test_unconfigured_alert_is_a_noop_and_does_not_fail_the_caller():
    result = _run({}, "critical", "grading backlog")
    assert result.returncode == 0
    assert "no alert destination configured" in result.stdout


def test_configured_command_receives_the_message():
    result = _run({"PROMPTCODE_ALERT_COMMAND": "/bin/echo"}, "critical", "subject", "detail")
    assert result.returncode == 0
    assert "critical: subject" in result.stdout
    assert "detail" in result.stdout
    assert "delivered via PROMPTCODE_ALERT_COMMAND" in result.stdout


def test_command_with_arguments_is_word_split():
    result = _run({"PROMPTCODE_ALERT_COMMAND": "/bin/echo prefix"}, "warning", "s")
    assert result.returncode == 0
    assert "prefix [promptcode] warning: s" in result.stdout


def test_failing_command_reports_failure():
    result = _run({"PROMPTCODE_ALERT_COMMAND": "/usr/bin/false"}, "critical", "x")
    assert result.returncode == 1
    assert "PROMPTCODE_ALERT_COMMAND failed" in result.stderr


def test_webhook_payload_is_json_with_the_message(monkeypatch, tmp_path):
    """The webhook path posts a structured JSON body (curl is replaced)."""
    import os

    capture = tmp_path / "payload.json"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    curl = fake_bin / "curl"
    curl.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  case \"$1\" in --data) shift; printf '%s' \"$1\" > \"${CAPTURE}\";; esac\n"
        "  shift\n"
        "done\n"
    )
    curl.chmod(0o755)
    env = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "CAPTURE": str(capture),
        "PROMPTCODE_ALERT_WEBHOOK_URL": "https://alerts.example.invalid/hook",
    }
    result = _run(env, "critical", "Grading backlog", "oldest queued 900s")
    assert result.returncode == 0, result.stderr
    assert "delivered via PROMPTCODE_ALERT_WEBHOOK_URL" in result.stdout
    import json

    payload = json.loads(capture.read_text())
    assert payload["severity"] == "critical"
    assert payload["subject"] == "Grading backlog"
    assert payload["detail"] == "oldest queued 900s"
    assert "Grading backlog" in payload["message"]
    assert payload["topic"] == "promptcode"


def test_webhook_failure_is_reported(monkeypatch, tmp_path):
    import os

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    curl = fake_bin / "curl"
    curl.write_text("#!/usr/bin/env bash\nexit 22\n")
    curl.chmod(0o755)
    env = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "PROMPTCODE_ALERT_WEBHOOK_URL": "https://alerts.example.invalid/hook",
    }
    result = _run(env, "critical", "x")
    assert result.returncode == 1
    assert "webhook delivery failed" in result.stderr


def test_health_check_alerts_before_exiting_on_failure(tmp_path):
    """A failing health check must reach the alert destination, not just cron mail."""
    import os

    deploy_dir = tmp_path / "deploy"
    backups_dir = deploy_dir / "backups"
    fake_bin = tmp_path / "bin"
    backups_dir.mkdir(parents=True)
    fake_bin.mkdir(parents=True)
    (deploy_dir / "docker-compose.yml").write_text("services: {}\n")
    (deploy_dir / "docker-compose.prod.yml").write_text("services: {}\n")
    (deploy_dir / ".last-deploy-status").write_text("success 1 abc\n")
    (backups_dir / ".last-success-timestamp").write_text("0\n")
    # Grading queue age is far past the alert threshold.
    docker = fake_bin / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "cmd=\"$*\"\n"
        "if [[ \"$cmd\" == *\"/metrics\"* ]]; then printf '200\\n';\n"
        "elif [[ \"$cmd\" == *\"worker_heartbeats\"* ]]; then printf '5\\n';\n"
        "elif [[ \"$cmd\" == *\"evaluation_jobs\"* ]]; then printf '0\\n';\n"
        "elif [[ \"$cmd\" == *\"interview_grading_jobs\"* ]]; then\n"
        "  if [[ \"$cmd\" == *\"status='failed'\"* ]]; then printf '0\\n';\n"
        "  elif [[ \"$cmd\" == *\"lease_expires_at\"* ]]; then printf '0\\n';\n"
        "  elif [[ \"$cmd\" == *\"MIN(created_at)\"* ]]; then printf '99999\\n';\n"
        "  else printf '0\\n'; fi\n"
        "else echo \"unexpected: $cmd\" >&2; exit 1; fi\n"
    )
    docker.chmod(0o755)
    alerts = tmp_path / "alerts.log"
    catcher = fake_bin / "alert-catcher"
    catcher.write_text("#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> \"${ALERT_LOG}\"\n")
    catcher.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["DEPLOY_DIR"] = str(deploy_dir)
    env["ALERT_LOG"] = str(alerts)
    env["PROMPTCODE_ALERT_COMMAND"] = str(catcher)
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts" / "check-prod-health.sh")],
        capture_output=True, text=True, check=False, env=env,
    )
    assert result.returncode == 1
    assert alerts.is_file(), "health check did not notify the alert destination"
    assert "critical" in alerts.read_text()
    assert "Grading backlog" in alerts.read_text()

