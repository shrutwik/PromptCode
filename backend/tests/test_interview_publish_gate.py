import json
import shutil
from pathlib import Path

import pytest

from scripts.run_interview_publish_gate import CONTRACT_PATH, run_gate

CHALLENGES = Path(__file__).resolve().parents[2] / 'challenges'


def test_all_questions_have_reviewed_publication_contracts():
    result = run_gate(challenges_dir=CHALLENGES)
    assert result['pass'], result
    assert result['question_count'] == 10


@pytest.mark.parametrize('change', ['missing-question', 'uncovered-requirement', 'manual-gap', 'invalid-floor'])
def test_contract_regressions_block_publication(tmp_path, change):
    contract = json.loads(CONTRACT_PATH.read_text())
    question = contract['questions']['catalog-suggest-latency']
    if change == 'missing-question':
        del contract['questions']['tenant-document-acl']
    elif change == 'uncovered-requirement':
        question['requirements']['large catalog'] = ['missing-test']
    elif change == 'manual-gap':
        question['manual_requirements'] = []
    else:
        question['min_visible_tests'] = True
    path = tmp_path / 'contract.json'
    path.write_text(json.dumps(contract))
    assert not run_gate(challenges_dir=CHALLENGES, contract_path=path)['pass']


@pytest.mark.parametrize('entry', ['src/missing.ts', 'SOLUTION.md', '../other-question/private.ts'])
def test_invalid_entry_files_block_question_publication(tmp_path, entry):
    source = tmp_path / 'challenges'
    shutil.copytree(CHALLENGES, source,
                    ignore=shutil.ignore_patterns('node_modules', '.venv', '__pycache__'))
    registry_path = source / 'interview-registry.json'
    registry = json.loads(registry_path.read_text())
    registry['challenges'][0]['entry_files'] = [entry]
    registry_path.write_text(json.dumps(registry))
    result = run_gate(challenges_dir=source)
    failed = [row for row in result['questions'] if not row['pass']]
    assert len(failed) == 1
    assert failed[0]['slug'] == 'invoice-status-transition'
    assert failed[0]['issues'] == ['Invalid candidate entry file: ' + entry]
