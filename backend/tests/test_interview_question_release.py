"""Release QA of reviewed practice suites, never authoritative candidate grading."""
from __future__ import annotations

import json
import os

import pytest
from trusted_reference_fixtures import reference_snapshot

from app.services.interview.registry import get_runner_config, list_challenges
from app.services.interview.runner import _parse_test_counts
from app.services.interview.trusted_evaluator import (
    _probe_command,
    _run_probe_container,
)
from scripts.run_interview_publish_gate import CONTRACT_PATH

VISIBLE_TEST_FLOORS = {slug: quality['min_visible_tests'] for slug, quality
                      in json.loads(CONTRACT_PATH.read_text())['questions'].items()}


def test_visible_suite_contract_covers_every_question():
    assert set(VISIBLE_TEST_FLOORS) == {c['slug'] for c in list_challenges()}


@pytest.mark.skipif(os.getenv('PROMPTCODE_AUDIT_DOCKER') != '1', reason='Isolated release QA requires Docker')
@pytest.mark.parametrize('slug', list(VISIBLE_TEST_FLOORS))
def test_live_reviewed_visible_suite_passes_without_skips(slug, tmp_path):
    path = reference_snapshot(slug, tmp_path / 'source')
    if get_runner_config(slug)['image'].endswith('python:latest'):
        probe = """import subprocess
r = subprocess.run(['python', '-m', 'pytest', '-q', '-ra'], capture_output=True, text=True, timeout=45)
result = {'exit_code': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr}
"""
    else:
        probe = """import {spawnSync} from 'node:child_process';import fs from 'node:fs';
const deps=fs.realpathSync('node_modules');fs.unlinkSync('node_modules');fs.mkdirSync('node_modules');
const copy=spawnSync('cp',['-as',deps+'/.','/workspace/node_modules/']);if(copy.status!==0)throw new Error('dependency links');
const r=spawnSync('node',['node_modules/vitest/vitest.mjs','run','--maxWorkers=1','--no-file-parallelism','--pool=forks'],{encoding:'utf8',timeout:45000});
return {exit_code:r.status,stdout:r.stdout,stderr:r.stderr};"""
    code, raw = _run_probe_container(path, _probe_command(slug, probe),
                                     image=get_runner_config(slug)['image'], timeout_seconds=60)
    assert code == 0, (slug, code)
    result = json.loads(raw)
    assert result['exit_code'] == 0, (slug, result)
    counts = _parse_test_counts(result['stdout'])
    assert counts['total'] >= VISIBLE_TEST_FLOORS[slug], (slug, result)
    assert counts['failed'] == counts['skipped'] == 0, (slug, result)
