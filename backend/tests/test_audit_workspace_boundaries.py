"""Regression checks for candidate filesystem boundaries; no product fixtures."""
from pathlib import Path

import pytest

from app.services.interview.workspace import (
    MAX_FILE_BYTES,
    contained_file,
    read_file,
    unified_diff_for_file,
    workspace_has_escape_link,
    write_file,
)


def test_candidate_cannot_read_write_or_diff_another_workspace(tmp_path):
    workspace = tmp_path / "candidate"
    other = tmp_path / "candidate-other"
    workspace.mkdir()
    other.mkdir()
    secret = other / "result.txt"
    secret.write_text("another candidate result")
    for rel in ("../candidate-other/result.txt", str(secret)):
        with pytest.raises(PermissionError):
            read_file(workspace, rel)
        with pytest.raises(PermissionError):
            write_file(workspace, rel, "tampered")
        with pytest.raises(PermissionError):
            unified_diff_for_file(workspace, workspace, rel)
    assert secret.read_text() == "another candidate result"


def test_candidate_symlink_is_rejected_by_api_and_runner(tmp_path):
    workspace = tmp_path / "candidate"
    workspace.mkdir()
    secret = tmp_path / "secret"
    secret.write_text("secret")
    (workspace / "link").symlink_to(secret)
    assert workspace_has_escape_link(workspace)
    for operation in (read_file, contained_file):
        with pytest.raises(PermissionError):
            operation(workspace, "link")
    with pytest.raises(PermissionError):
        write_file(workspace, "link", "tampered")
    assert secret.read_text() == "secret"


@pytest.mark.parametrize("name", ["package.json", "package-lock.json", "conftest.py", "pytest.ini", ".env", "run.sh"])
def test_candidate_cannot_replace_runner_control_files(tmp_path, name):
    target = tmp_path / name
    target.write_text("trusted")
    with pytest.raises(PermissionError):
        write_file(tmp_path, name, "tampered")
    assert target.read_text() == "trusted"


def test_file_limit_counts_bytes_before_writing(tmp_path):
    with pytest.raises(ValueError, match="too large"):
        write_file(tmp_path, "source.py", "é" * (MAX_FILE_BYTES // 2 + 1))
    assert not (tmp_path / "source.py").exists()
    write_file(tmp_path, "source.py", "print('ok')")
    assert read_file(tmp_path, "source.py") == "print('ok')"
