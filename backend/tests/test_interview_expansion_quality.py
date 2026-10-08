"""Local authoring QA for reviewed original Python references, not candidate grading.

The production evaluator still executes frozen submissions in its isolated runner.
These subprocesses contain only reviewed test-owned reference code or the known
incident starters and never produce signed evaluation evidence.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from expansion_reference_fixtures import EDGE_MUTATIONS, MUTATIONS, REFERENCE_SOURCES
from trusted_reference_fixtures import reference_snapshot

from app.services.interview.registry import challenge_dir
from app.services.interview.trusted_cases import cases_for


def observe(path: Path, probe: str):
    adapter = (
        "import sys,json;sys.path.insert(0," + repr(str(path)) + ");ns={};"
        "exec(" + repr(probe) + ",ns);sys.stdout.write(json.dumps(ns['result'],allow_nan=False))"
    )
    result = subprocess.run([sys.executable, '-I', '-c', adapter], cwd=path,
                            capture_output=True, text=True, timeout=6)
    if result.returncode:
        return False, result.stderr
    try:
        return True, json.loads(result.stdout)
    except ValueError:
        return False, result.stdout


@pytest.mark.parametrize('slug', [slug for slug in REFERENCE_SOURCES if 'engine.py' in REFERENCE_SOURCES[slug]])
def test_reviewed_expansion_passes_visible_suite(slug, tmp_path):
    source = reference_snapshot(slug, tmp_path / 'reference')
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-ra'], cwd=source,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, (slug, result.stdout, result.stderr)
    assert 'skipped' not in result.stdout


@pytest.mark.parametrize('slug', [slug for slug in REFERENCE_SOURCES if 'engine.py' in REFERENCE_SOURCES[slug]])
def test_reviewed_expansion_passes_independent_cases_and_starter_does_not(slug, tmp_path):
    source = reference_snapshot(slug, tmp_path / 'reference')
    starter_matches = []
    for case in cases_for(slug):
        ok, actual = observe(source, case.probe)
        assert ok, (slug, case.id, actual)
        expected = json.loads(json.dumps(case.expected))
        assert actual == expected, (slug, case.id, actual, expected)
        ok, actual = observe(challenge_dir(slug), case.probe)
        starter_matches.append(ok and actual == expected)
    assert not all(starter_matches), 'Starter must contain a real observable defect'


@pytest.mark.parametrize('slug', [slug for slug in REFERENCE_SOURCES if 'engine.py' in REFERENCE_SOURCES[slug]])
@pytest.mark.parametrize('mutations', [MUTATIONS, EDGE_MUTATIONS], ids=['baseline', 'edge'])
def test_expansion_rejects_plausible_wrong_repairs(slug, mutations, tmp_path):
    source = reference_snapshot(slug, tmp_path / 'reference')
    file, old, new, case_id = mutations[slug]
    p = source / file
    text = p.read_text()
    assert old in text
    p.write_text(text.replace(old, new))
    case = next(c for c in cases_for(slug) if c.id == case_id)
    ok, actual = observe(source, case.probe)
    assert not ok or actual != json.loads(json.dumps(case.expected)), (slug, case_id)
