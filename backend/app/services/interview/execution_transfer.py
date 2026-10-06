"""Bounded source transfer; callers never choose execution-host paths or mounts."""
from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, Field, model_validator

from .snapshot import _contents, _source_files, manifest_digest
from .workspace import MAX_FILE_BYTES, SKIP_DIR_NAMES
from .workspace_quota import SOURCE_BYTES, SOURCE_FILES
from .registry import is_blocked_path

MAX_REQUEST_BYTES = 30 * 1024 * 1024


class SourceFile(BaseModel):
    model_config = {"extra": "forbid"}
    path: str = Field(min_length=1, max_length=500)
    data: str = Field(max_length=4 * ((MAX_FILE_BYTES + 2) // 3))

    @model_validator(mode="after")
    def safe_file(self):
        path = PurePosixPath(self.path)
        if (not path.parts or path.is_absolute() or self.path != path.as_posix() or "\\" in self.path
                or any(part in {".", "..", *SKIP_DIR_NAMES} for part in path.parts)
                or not re.fullmatch(r"[^\x00-\x1f\x7f]+", self.path)
                or is_blocked_path(self.path)):
            raise ValueError("Invalid source path")
        self.decoded()
        return self

    def decoded(self) -> bytes:
        try:
            data = base64.b64decode(self.data, validate=True)
        except (ValueError, TypeError):
            raise ValueError("Invalid source encoding") from None
        if len(data) > MAX_FILE_BYTES:
            raise ValueError("Source file exceeds limit")
        return data


class SourceBundle(BaseModel):
    model_config = {"extra": "forbid"}
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    files: list[SourceFile] = Field(min_length=1, max_length=SOURCE_FILES)

    @model_validator(mode="after")
    def bounded_and_verified(self):
        manifest = []
        paths = set()
        total = 0
        for item in self.files:
            if item.path in paths:
                raise ValueError("Duplicate source path")
            paths.add(item.path)
            data = item.decoded()
            total += len(data)
            if total > SOURCE_BYTES:
                raise ValueError("Source exceeds quota")
            manifest.append({"path": item.path, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
        if any(str(parent) in paths for path in paths for parent in PurePosixPath(path).parents):
            raise ValueError("Source path conflicts with directory")
        if manifest_digest(sorted(manifest, key=lambda item: item["path"])) != self.digest:
            raise ValueError("Source digest mismatch")
        return self

    def materialize(self, root: Path) -> Path:
        """root must be a fresh service-owned temporary directory."""
        source = root / self.digest / "source"
        source.mkdir(parents=True)
        for item in self.files:
            target = source / item.path
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                output.write(item.decoded())
            target.chmod(0o444)
        return source


def bundle_source(root: Path) -> SourceBundle:
    files = []
    manifest = []
    total = 0
    for rel, path in _source_files(root):
        data = _contents(path)
        total += len(data)
        if total > SOURCE_BYTES or len(files) >= SOURCE_FILES:
            raise ValueError("Source exceeds quota")
        files.append(SourceFile(path=rel, data=base64.b64encode(data).decode("ascii")))
        manifest.append({"path": rel, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
    return SourceBundle(digest=manifest_digest(sorted(manifest, key=lambda item: item["path"])), files=files)
