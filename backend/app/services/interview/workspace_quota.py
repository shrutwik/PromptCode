"""Persistent upload/dependency budgets; candidate execution additionally uses tmpfs."""
import os
import fcntl
import shutil
from contextlib import contextmanager
from pathlib import Path
from fastapi import HTTPException
from app.core.config import get_settings

SOURCE_BYTES = 20 * 1024 * 1024
SOURCE_FILES = 1000
DEPENDENCY_BYTES = 128 * 1024 * 1024
DEPENDENCY_FILES = 20000
DEPENDENCY_DIRS = {'node_modules', '.venv', 'venv'}


def retained_bytes(root: Path) -> int:
    """Count all persistent artifacts, including dependencies and frozen source."""
    total = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if not (Path(directory) / name).is_symlink()]
        for name in files:
            path = Path(directory) / name
            if not path.is_symlink():
                try:
                    total += path.stat().st_size
                except FileNotFoundError:  # Cleanup can concurrently remove artifacts.
                    continue
    return total


@contextmanager
def storage_capacity(additional_bytes: int):
    """Hold the shared host lock until a persistent write completes.

    All API/worker replicas sharing artifacts must share this root. Candidate
    execution writes only to bounded ephemeral storage, outside this budget.
    """
    from app.services.interview.workspace import workspace_root
    root = workspace_root()
    with (root / '.storage.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        settings = get_settings()
        additional_bytes = max(0, additional_bytes)
        if (retained_bytes(root) + additional_bytes > settings.interview_storage_max_bytes
                or shutil.disk_usage(root).free - additional_bytes < settings.interview_storage_min_free_bytes):
            raise HTTPException(507, 'Interview storage capacity reached. Please try again later.',
                                headers={'Retry-After': '60'})
        yield


def usage(root: Path):
    source_bytes = source_files = dependency_bytes = dependency_files = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            if (Path(directory) / name).is_symlink():
                raise ValueError('Workspace link blocked')
        dependency = bool(set(Path(directory).relative_to(root).parts) & DEPENDENCY_DIRS)
        for name in files:
            path = Path(directory) / name
            if path.is_symlink():
                raise ValueError('Workspace link blocked')
            size = path.stat().st_size
            if dependency:
                dependency_bytes += size
                dependency_files += 1
            else:
                source_bytes += size
                source_files += 1
            if source_bytes > SOURCE_BYTES or source_files > SOURCE_FILES or dependency_bytes > DEPENDENCY_BYTES or dependency_files > DEPENDENCY_FILES:
                raise ValueError('Session workspace quota exceeded')
    return source_bytes, source_files


def check_upload(root, path, content_bytes):
    total, files = usage(root)
    exists = path.is_file()
    old_size = path.stat().st_size if exists else 0
    if total - old_size + content_bytes > SOURCE_BYTES or files + (not exists) > SOURCE_FILES:
        raise ValueError('Session source quota exceeded')
