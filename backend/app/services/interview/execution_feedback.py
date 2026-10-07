"""Advisory execution feedback; no candidate process is an authoritative grader."""
import json
from typing import Any

MAX_REPORT_BYTES = 1_000_000


def read_report(container, path="/tmp/promptcode-report.json"):
    # Docker archive/copy omits tmpfs content. Read bounded bytes while it is mounted.
    result = container.exec_run(["/usr/bin/head", "-c", str(MAX_REPORT_BYTES + 1), path], user="10001:10001")
    if result.exit_code != 0 or len(result.output) > MAX_REPORT_BYTES:
        raise ValueError("Missing or oversized report")
    return json.loads(result.output)


def complete_report(report, expected_ids):
    if not isinstance(expected_ids, list) or not expected_ids or len(expected_ids) != len(set(expected_ids)):
        return False
    if not isinstance(report, dict) or report.get('version') != 1 or report.get('complete') is not True or report.get('exit_code') != 0:
        return False
    records = report.get('records')
    if not isinstance(records, list):
        return False
    expected = {(test_id, phase) for test_id in expected_ids for phase in ('setup', 'call', 'teardown')}
    actual = set()
    for record in records:
        if not isinstance(record, dict) or record.get('outcome') != 'passed':
            return False
        key = (record.get('id'), record.get('phase'))
        if key not in expected or key in actual:
            return False
        actual.add(key)
    return actual == expected


def advisory_summary(summary: dict[str, Any] | None) -> dict[str, Any]:
    return {**(summary or {}), 'advisory': True, 'authoritative': False,
            'feedback_kind': 'advisory_practice', 'correctness_visible': None,
            'notice': 'Practice feedback only. Candidate execution cannot establish authoritative correctness.'}


def advisory_scoring(scored: dict[str, Any]) -> dict[str, Any]:
    # Remove every numeric grade at the scoring boundary, including legacy inputs.
    rubric = {key: {**value, 'score': 0.0, 'advisory': True,
                   'evidence': 'Advisory practice observation; no authoritative grade.'}
              for key, value in (scored.get('rubric') or {}).items()}
    return {**scored, 'total_score': 0.0, 'rubric': rubric,
            'metrics': {**scored.get('metrics', {}), 'authoritative': False, 'advisory': True},
            'test_summary': advisory_summary(scored.get('test_summary'))}
