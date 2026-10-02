"""Known grading attacks: expected failures are security failures, not passes."""
import asyncio
import os

import pytest

from app.services.interview.runner import IsolatedRunner
from app.services.interview.workspace import write_file


def test_candidate_cannot_rewrite_tests_through_editor(tmp_path):
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests/test_grade.py').write_text('def test_grade(): assert False\n')
    with pytest.raises(PermissionError):
        write_file(tmp_path, 'tests/test_grade.py', 'def test_grade(): assert True\n')


@pytest.mark.skipif(os.getenv('PROMPTCODE_AUDIT_DOCKER') != '1', reason='Live Docker audit opt-in required')
@pytest.mark.xfail(strict=True, reason='B6 OPEN: candidate can forge passing stdout and exit pytest process successfully')
def test_candidate_cannot_forge_grader_success(tmp_path):
    workspace = tmp_path / 'candidate'
    workspace.mkdir(mode=0o777)
    workspace.chmod(0o777)
    (workspace / 'test_grade.py').write_text('import solution\ndef test_grade(): assert solution.answer() == 42\n')
    (workspace / 'solution.py').write_text("import os\nfrom pathlib import Path\nPath('/workspace/test_grade.py').write_text('def test_grade(): assert True\\n')\nPath('/workspace/results.json').write_text('{\"ok\":true,\"passed\":999}')\nos.write(1,b'999 passed in 0.01s\\n')\nos._exit(0)\n")
    result = asyncio.run(IsolatedRunner().run_tests(workspace, 'pytest -q', runner_config={'image':'promptcode-runner-python:latest','timeoutSeconds':10,'memoryMb':128}))
    assert not (workspace / 'results.json').exists()
    assert 'assert solution.answer() == 42' in (workspace / 'test_grade.py').read_text()
    assert result['ok'] is False, result


@pytest.mark.parametrize('path', ['test_grade.py', 'tests/grade.py', '__tests__/grade.ts', 'src/grade.test.ts', 'src/grade.spec.js'])
def test_trusted_test_paths_are_frozen(tmp_path, path):
    with pytest.raises(PermissionError): write_file(tmp_path, path, 'tampered')


def test_candidate_implementation_remains_editable(tmp_path):
    write_file(tmp_path, 'src/solution.py', 'answer = 42')
    assert (tmp_path / 'src/solution.py').read_text() == 'answer = 42'
