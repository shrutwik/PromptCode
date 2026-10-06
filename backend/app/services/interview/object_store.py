"""Durable object storage for immutable interview submissions.

Only one namespace exists: ``submitted/{session_id}/{source_digest}/{rel_path}``,
never a host path. Submission bytes are written to the private Supabase Storage
bucket (authenticated Storage REST API, service-role bearer token, no public or
signed URL) when ``storage_backend=supabase``, and to a local directory otherwise
so filesystem development and the Docker path keep working.

A submission is committed by uploading its ``manifest.json`` LAST; readers treat
the manifest as the commit marker, so an interrupted upload never reads back as a
complete submission. Puts are idempotent (``x-upsert``) with a bounded retry and
backoff, and a single object may not exceed ``supabase_max_object_bytes``.
"""
from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path, PurePosixPath

import httpx

from app.core.config import get_settings

MANIFEST_NAME = "manifest.json"

_RETRY_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
_MAX_KEY_BYTES = 1024


class ObjectStoreError(RuntimeError):
    """Object storage is unavailable or answered unexpectedly."""


class ObjectNotFound(ObjectStoreError):
    """The requested key does not exist."""


class ObjectTooLarge(ObjectStoreError):
    """A single object exceeded the configured per-object byte cap."""


def normalize_rel_path(rel_path: str) -> str:
    """Reject anything that could escape the submission namespace."""
    raw = str(rel_path).replace("\\", "/")
    path = PurePosixPath(raw)
    if (not raw or raw != path.as_posix() or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or any(ord(char) < 32 or ord(char) == 127 for char in raw)):
        raise ValueError("Invalid object path")
    return path.as_posix()


def submission_prefix(session_id, source_digest) -> str:
    session, digest = str(session_id).strip(), str(source_digest).strip()
    if not session or not digest or any(c in session + digest for c in "/\\"):
        raise ValueError("Invalid submission identity")
    return f"submitted/{session}/{digest}"


def submission_key(session_id, source_digest, rel_path: str) -> str:
    return f"{submission_prefix(session_id, source_digest)}/{normalize_rel_path(rel_path)}"


def manifest_key(session_id, source_digest) -> str:
    return f"{submission_prefix(session_id, source_digest)}/{MANIFEST_NAME}"


def _validate_key(key: str) -> str:
    raw = str(key)
    if (not raw or raw.startswith("/") or raw.endswith("/") or "//" in raw or "\\" in raw
            or len(raw.encode("utf-8")) > _MAX_KEY_BYTES
            or any(part in {"", ".", ".."} for part in raw.split("/"))
            or any(ord(char) < 32 or ord(char) == 127 for char in raw)):
        raise ValueError("Invalid object key")
    return raw


def _max_object_bytes() -> int:
    return int(getattr(get_settings(), "supabase_max_object_bytes", 0) or 0)


def _check_size(key: str, data: bytes, limit: int) -> None:
    if limit and len(data) > limit:
        raise ObjectTooLarge(f"Object {key} exceeds the {limit} byte per-object limit")


class LocalObjectStore:
    """Filesystem-backed store for local development and the Docker path.

    Keys are the same provider-neutral strings the managed backend uses, and a put
    is atomic (temp file + ``os.replace``) so a crash never exposes a partially
    written object as complete.
    """

    def __init__(self, root: Path, *, max_object_bytes: int | None = None):
        self.root = Path(root)
        self.max_object_bytes = _max_object_bytes() if max_object_bytes is None else int(max_object_bytes)

    def _path(self, key: str) -> Path:
        return self.root / _validate_key(key)

    def put(self, key: str, data: bytes) -> None:
        payload = bytes(data)
        path = self._path(key)
        _check_size(key, payload, self.max_object_bytes)
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".put-")
        try:
            with os.fdopen(handle, "wb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
        except BaseException:
            if os.path.exists(temporary):
                os.unlink(temporary)
            raise

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except (FileNotFoundError, NotADirectoryError):
            raise ObjectNotFound(key) from None

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete_prefix(self, prefix: str) -> int:
        base = self._path(prefix)
        if not base.exists():
            return 0
        if base.is_file():
            base.unlink()
            return 1
        removed = sum(1 for path in base.rglob("*") if path.is_file())
        import shutil

        shutil.rmtree(base)
        return removed


class SupabaseObjectStore:
    """Private-bucket Supabase Storage REST client.

    Uses the authenticated object endpoint ``/storage/v1/object/{bucket}/{key}``
    with ``Authorization: Bearer <service-role>``. Objects stay private.
    """

    def __init__(
        self,
        *,
        base_url: str,
        service_role_key: str,
        bucket: str,
        timeout: float = 30.0,
        max_object_bytes: int | None = None,
        retries: int = 3,
        backoff_seconds: float = 0.5,
        transport: httpx.BaseTransport | None = None,
    ):
        self.bucket = str(bucket).strip().strip("/")
        if not self.bucket or "/" in self.bucket:
            raise ObjectStoreError("Invalid Supabase storage bucket")
        self.max_object_bytes = _max_object_bytes() if max_object_bytes is None else int(max_object_bytes)
        self.retries = max(1, int(retries))
        self.backoff_seconds = max(0.0, float(backoff_seconds))
        credentials = str(service_role_key).strip()
        if not credentials:
            raise ObjectStoreError("Supabase service role key is required for object storage")
        self._client = httpx.Client(
            base_url=str(base_url).rstrip("/") + "/storage/v1",
            timeout=timeout,
            transport=transport,
            headers={"Authorization": "Bearer " + credentials, "apikey": credentials},
        )

    @classmethod
    def from_settings(cls, settings=None, **kwargs) -> "SupabaseObjectStore":
        settings = settings or get_settings()
        return cls(
            base_url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key,
            bucket=settings.supabase_storage_bucket,
            timeout=float(settings.supabase_storage_timeout_seconds),
            max_object_bytes=int(settings.supabase_max_object_bytes),
            **kwargs,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SupabaseObjectStore":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def _object_url(self, key: str) -> str:
        return f"/object/{self.bucket}/{_validate_key(key)}"

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Issue one bounded, retried request; transient failures back off."""
        attempt = 0
        while True:
            try:
                response = self._client.request(method, url, **kwargs)
            except httpx.TransportError as exc:
                if attempt >= self.retries - 1:
                    raise ObjectStoreError("Object storage request failed") from exc
            else:
                if response.status_code not in _RETRY_STATUS or attempt >= self.retries - 1:
                    return response
            time.sleep(self.backoff_seconds * (2 ** attempt))
            attempt += 1

    @staticmethod
    def _is_missing(response: httpx.Response) -> bool:
        if response.status_code == 404:
            return True
        if response.status_code != 400:
            return False
        body = response.text.lower()
        return "not found" in body or '"404"' in body or "nosuchkey" in body

    def put(self, key: str, data: bytes) -> None:
        payload = bytes(data)
        _check_size(key, payload, self.max_object_bytes)
        response = self._request(
            "POST", self._object_url(key), content=payload,
            headers={"Content-Type": "application/octet-stream", "x-upsert": "true"},
        )
        if response.status_code not in (200, 201):
            raise ObjectStoreError(f"Object storage upload failed ({response.status_code})")

    def get(self, key: str) -> bytes:
        response = self._request("GET", self._object_url(key))
        if self._is_missing(response):
            raise ObjectNotFound(key)
        if response.status_code != 200:
            raise ObjectStoreError(f"Object storage download failed ({response.status_code})")
        return response.content

    def exists(self, key: str) -> bool:
        response = self._request("HEAD", self._object_url(key))
        if response.status_code in (200, 204):
            return True
        if self._is_missing(response):
            return False
        if response.status_code in (400, 405):
            # Some frontends do not implement HEAD; fall back to a full read.
            try:
                self.get(key)
                return True
            except ObjectNotFound:
                return False
        raise ObjectStoreError(f"Object storage head failed ({response.status_code})")


def local_objects_root() -> Path:
    """Per-container cache root used by the filesystem backend."""
    from app.services.interview.workspace import workspace_root

    return workspace_root() / ".objects"


def object_store_is_managed() -> bool:
    """Whether the durable store lives outside this container."""
    settings = get_settings()
    return str(getattr(settings, "storage_backend", "filesystem")).strip().lower() == "supabase"


def durable_submission_required() -> bool:
    """Whether a submission must outlive this container.

    True for managed object storage and for Modal, where containers are ephemeral
    so the host path recorded at submit time is meaningless on the next request.
    """
    settings = get_settings()
    return (object_store_is_managed()
            or str(getattr(settings, "execution_backend", "")).strip().lower() == "modal")


_cached_store = None
_cached_store_key = None


def get_object_store():
    """Select the durable object store for the configured backend.

    The store is cached per process. ``SupabaseObjectStore`` owns an ``httpx.Client``
    (a connection pool), so constructing one per call would leak a pool for every
    submission and every grading attempt inside a long-lived container. The cache key
    covers the URL and bucket, and a changed key closes the previous client.
    """
    global _cached_store, _cached_store_key
    settings = get_settings()
    if object_store_is_managed():
        # The class is part of the key so a replaced/subclassed store (as tests do to
        # stub the transport) builds a fresh instance instead of reusing a stale one.
        key = (
            SupabaseObjectStore,
            str(settings.supabase_url),
            str(settings.supabase_storage_bucket),
        )
        if _cached_store is None or _cached_store_key != key:
            previous, _cached_store = _cached_store, SupabaseObjectStore.from_settings(settings)
            _cached_store_key = key
            if previous is not None:
                previous.close()
        return _cached_store
    # The local store holds no pooled resource, so constructing it is free.
    return LocalObjectStore(local_objects_root())
