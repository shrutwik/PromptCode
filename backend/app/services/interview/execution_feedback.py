"""Advisory execution feedback; no candidate process is an authoritative grader."""
import json

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


def candidate_case_rows(records):
    """One visible row per test, with duration and a short failure excerpt."""
    grouped: dict[str, dict] = {}
    order: list[str] = []
    for record in records or []:
        if not isinstance(record, dict):
            continue
        test_id = str(record.get("id") or "").strip()
        if not test_id:
            continue
        if test_id not in grouped:
            grouped[test_id] = {
                "id": test_id,
                "outcome": "passed",
                "duration_ms": 0,
                "output": "",
            }
            order.append(test_id)
        row = grouped[test_id]
        row["duration_ms"] += int(record.get("duration_ms") or 0)
        outcome = str(record.get("outcome") or "")
        if outcome and outcome != "passed":
            row["outcome"] = outcome
        excerpt = str(record.get("output") or "").strip()
        if excerpt and record.get("phase") == "call":
            row["output"] = excerpt[:500]
    return [grouped[test_id] for test_id in order]


def missing_expected_ids(report, expected_ids):
    if not isinstance(expected_ids, list):
        return []
    if not isinstance(report, dict):
        return [f"{test_id} [report]" for test_id in expected_ids]
    actual = set()
    for record in report.get("records") or []:
        if isinstance(record, dict) and record.get("outcome") == "passed":
            actual.add((record.get("id"), record.get("phase")))
    missing = []
    for test_id in expected_ids:
        for phase in ("setup", "call", "teardown"):
            if (test_id, phase) not in actual:
                missing.append(f"{test_id} [{phase}]")
                break
    return missing


def practice_notice(*, report, expected_ids, exit_code, timed_out, truncated, report_ok, is_python):
    notes = []
    if truncated:
        notes.append("Output truncated. The run produced more text than the limit.")
    if timed_out:
        notes.append("The run timed out before it finished.")
    if exit_code == 0 and not report_ok:
        if not is_python:
            notes.append(
                "This run did not produce the required test report, so it cannot be marked passed."
            )
        elif not expected_ids:
            notes.append(
                "No expected test inventory is configured, so this run cannot be marked passed."
            )
        else:
            missing = missing_expected_ids(report, expected_ids)
            if missing:
                shown = ", ".join(missing[:8])
                extra = "" if len(missing) <= 8 else f" (+{len(missing) - 8} more)"
                notes.append(
                    f"Missing expected test IDs ({shown}{extra}). The run fails closed."
                )
            else:
                notes.append(
                    "The test report was incomplete, so this run cannot be marked passed."
                )
    return " ".join(notes)


def advisory_summary(summary):
    return {**(summary or {}), 'advisory': True, 'authoritative': False,
            'feedback_kind': 'advisory_practice', 'correctness_visible': None,
            'notice': 'Practice feedback only. Candidate execution cannot establish authoritative correctness.'}


def advisory_scoring(scored):
    # Remove every numeric grade at the scoring boundary, including legacy inputs.
    rubric = {key: {**value, 'score': 0.0, 'advisory': True,
                   'evidence': 'Advisory practice observation; no authoritative grade.'}
              for key, value in (scored.get('rubric') or {}).items()}
    return {**scored, 'total_score': 0.0, 'rubric': rubric,
            'metrics': {**scored.get('metrics', {}), 'authoritative': False, 'advisory': True},
            'test_summary': advisory_summary(scored.get('test_summary'))}
