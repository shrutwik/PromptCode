"""Platform-supplied pytest reporter. Completeness mitigation, not a trust boundary."""
import json
from pathlib import Path

_records = []


def pytest_runtest_logreport(report):
    _records.append({"id": report.nodeid, "phase": report.when, "outcome": report.outcome})


def pytest_sessionfinish(session, exitstatus):
    Path('/tmp/promptcode-report.json').write_text(json.dumps({
        "version": 1, "complete": True, "exit_code": int(exitstatus), "records": _records,
    }))
