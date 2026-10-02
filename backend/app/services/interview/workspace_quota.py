"""Persistent upload/dependency budgets; candidate execution additionally uses tmpfs."""
import os
from pathlib import Path

SOURCE_BYTES = 20 * 1024 * 1024
SOURCE_FILES = 1000
DEPENDENCY_BYTES = 128 * 1024 * 1024
DEPENDENCY_FILES = 20000
DEPENDENCY_DIRS = {'node_modules', '.venv', 'venv'}


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
