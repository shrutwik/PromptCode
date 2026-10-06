"""STUBBED / LOCAL integration test for the managed stack — NOT live verification.

This drives the complete candidate workflow through the real FastAPI routes with
the managed stack *configured* (``PROMPTCODE_EXECUTION_BACKEND=modal``,
``PROMPTCODE_STORAGE_BACKEND=supabase``) while both external providers are stubbed
locally:

* the ``modal`` SDK is injected through ``sys.modules`` (the pattern from
  ``tests/test_modal_execution_backend.py``), so no Modal account, token, image or
  sandbox is involved;
* Supabase Storage is exercised through the real :class:`SupabaseObjectStore` code
  path (URL building, bearer header, upsert, retry, size checks) with only the
  ``httpx`` transport replaced by ``httpx.MockTransport`` (the pattern from
  ``tests/test_managed_storage.py``), so no network call leaves the process.

What this proves: the route/DB/object-store/sandbox-dispatch wiring of the managed
stack is internally consistent end to end, that hydration rebuilds a lost
workspace, and that ownership is enforced on the file routes.

What this does NOT prove: anything about the real Modal sandbox isolation
(``block_network`` is asserted as a create argument, not observed), the real
Supabase bucket (no bucket is created; the private bucket's server-side policy is
untested), Vercel routing, TLS, Postgres-specific SQL, or production startup
validation. Those require live accounts and are explicitly out of scope here.

The managed deployment deliberately leaves ``PROMPTCODE_RUNNER`` at ``local``
(see ``.env.example`` and ``docs/managed-deployment.md``) because candidate code is
supposed to be executed by the Modal execution backend, not by the API process.
This test is configured that way on purpose.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import sys
import threading
import types
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.services.interview.object_store import SupabaseObjectStore

PASSWORD = "Str0ng!P@ssw0rd"
BUCKET = "promptcode-private"
SERVICE_ROLE = "stub-service-role-key-for-tests"
NODE_IMAGE = "registry.example/runner-node:1"
PYTHON_IMAGE = "registry.example/runner-python:1"
SIGNING_KEY = "managed-integration-grading-signing-key-0123456789abcdef"
MANIFEST_NAME = "manifest.json"


# --------------------------------------------------------------------------- #
# Stubbed Supabase Storage transport
# --------------------------------------------------------------------------- #


class StubBucket:
    """In-memory stand-in for the private bucket's authenticated object endpoints."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.calls: list[tuple[str, str, str | None]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        authorization = request.headers.get("Authorization")
        self.calls.append((request.method, path, authorization))
        assert path.startswith("/storage/v1/object/"), path
        bucket, key = path[len("/storage/v1/object/"):].split("/", 1)
        assert bucket == BUCKET, f"objects must go to the configured private bucket, got {bucket}"
        if request.method == "POST":
            assert request.headers.get("x-upsert") == "true"
            self.objects[key] = request.content
            return httpx.Response(200, json={"Key": key})
        if request.method == "GET":
            if key not in self.objects:
                return httpx.Response(404, json={"statusCode": "404", "error": "not_found"})
            return httpx.Response(200, content=self.objects[key])
        if request.method == "HEAD":
            if key not in self.objects:
                return httpx.Response(404, json={"statusCode": "404", "error": "not_found"})
            return httpx.Response(200)
        raise AssertionError(f"unexpected request {request.method} {path}")

    def keys(self) -> list[str]:
        return sorted(self.objects)


# --------------------------------------------------------------------------- #
# Stubbed Modal SDK
# --------------------------------------------------------------------------- #


class _FakeStream:
    def __init__(self, data: bytes) -> None:
        self._data = bytearray(data)

    def read(self, size: int = -1) -> bytes:
        if not self._data:
            return b""
        take = len(self._data) if size is None or size < 0 else size
        chunk = bytes(self._data[:take])
        del self._data[:take]
        return chunk


class _FakeProcess:
    """Process stub whose output is chosen by the sandbox that produced it."""

    def __init__(self, *, stdout: bytes = b"", stderr: bytes = b"", exit_code: int = 0,
                 started: threading.Event | None = None, release: threading.Event | None = None) -> None:
        self.stdout = _FakeStream(stdout)
        self.stderr = _FakeStream(stderr)
        self._exit_code = exit_code
        self._started = started
        self._release = release

    def wait(self) -> int:
        if self._started is not None:
            self._started.set()
        if self._release is not None:
            assert self._release.wait(10), "sandbox stub was never released"
        return self._exit_code


class _FakeFilesystem:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.directories: set[str] = set()

    def make_directory(self, remote_path: str, *, create_parents: bool = True) -> None:
        self.directories.add(str(remote_path))

    def write_bytes(self, data: bytes, remote_path: str) -> None:
        self.files[str(remote_path)] = bytes(data)

    def read_bytes(self, remote_path: str) -> bytes:
        return self.files[str(remote_path)]


class _FakeSandbox:
    def __init__(self, module: "FakeModal") -> None:
        self.filesystem = _FakeFilesystem()
        self.terminated = False
        self.exec_argv: tuple[str, ...] | None = None
        self.exec_kwargs: dict[str, Any] | None = None
        self._module = module

    def exec(self, *argv: str, **kwargs: Any) -> _FakeProcess:
        self.exec_argv = argv
        self.exec_kwargs = kwargs
        # The advisory Modal wrapper runs candidate code through ``sh -c``; the
        # trusted probe runs the interpreter directly.
        if argv and argv[0] == "sh":
            return _FakeProcess(stdout=b"1 passed\n", exit_code=0)
        return _FakeProcess(stdout=b'{"ok": true}', exit_code=0)

    def terminate(self, **_kwargs: Any) -> None:
        self.terminated = True


class FakeModal(types.ModuleType):
    """Minimal ``modal`` surface used by ``ModalSandboxBackend``."""

    def __init__(self) -> None:
        super().__init__("modal")
        self.created: list[_FakeSandbox] = []
        self.create_kwargs: dict[str, Any] = {}
        self.images: list[str] = []
        self.app_names: list[str] = []
        self.create_error: BaseException | None = None
        self.block_create: threading.Event | None = None
        self.release_create: threading.Event | None = None
        self.create_entered = threading.Event()
        self.App = types.SimpleNamespace(lookup=self._lookup)
        self.Image = types.SimpleNamespace(from_registry=self._from_registry)
        self.Sandbox = types.SimpleNamespace(create=self._create)

    def _lookup(self, name: str, **_kwargs: Any) -> Any:
        self.app_names.append(name)
        return SimpleNamespace(name=name)

    def _from_registry(self, reference: str, **_kwargs: Any) -> Any:
        self.images.append(str(reference))
        return SimpleNamespace(reference=reference)

    def _create(self, *_args: Any, **kwargs: Any) -> _FakeSandbox:
        self.create_kwargs = kwargs
        if self.create_error is not None:
            raise self.create_error
        sandbox = _FakeSandbox(self)
        self.created.append(sandbox)
        self.create_entered.set()
        if self.block_create is not None:
            assert self.block_create.wait(10), "sandbox create stub was never released"
        return sandbox


# --------------------------------------------------------------------------- #
# application fixture
# --------------------------------------------------------------------------- #


def _configure_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in {
        "PROMPTCODE_DEBUG": "true",
        "PROMPTCODE_JWT_SECRET": "managed-integration-test-secret",
        # Faithful to the documented managed deployment: candidate code is executed
        # by the Modal execution backend, not by the API process.
        "PROMPTCODE_RUNNER": "local",
        "PROMPTCODE_ALLOW_UNSAFE_LOCAL_RUNNER": "false",
        "PROMPTCODE_EXECUTION_BACKEND": "modal",
        "PROMPTCODE_MODAL_SANDBOX_IMAGE_NODE": NODE_IMAGE,
        "PROMPTCODE_MODAL_SANDBOX_IMAGE_PYTHON": PYTHON_IMAGE,
        "PROMPTCODE_STORAGE_BACKEND": "supabase",
        "PROMPTCODE_SUPABASE_URL": "https://stub.supabase.co",
        "PROMPTCODE_SUPABASE_SERVICE_ROLE_KEY": SERVICE_ROLE,
        "PROMPTCODE_SUPABASE_STORAGE_BUCKET": BUCKET,
        "PROMPTCODE_SUPABASE_STORAGE_TIMEOUT_SECONDS": "5",
        "PROMPTCODE_GRADING_SIGNING_KEY": SIGNING_KEY,
        "PROMPTCODE_INTERVIEW_WORKSPACE_ROOT": str(tmp_path / "workspaces"),
        # Pin the provider pair so the test does not depend on a developer's `.env`
        # (an inconsistent pair is a hard validation error, see config.py).
        "PROMPTCODE_AI_PROVIDER": "deepseek",
        "PROMPTCODE_AI_BASE_URL": "https://api.deepseek.com",
    }.items():
        monkeypatch.setenv(name, value)


def _stub_supabase_transport(monkeypatch: pytest.MonkeyPatch, bucket: StubBucket) -> None:
    """Keep the real store class; replace only the HTTP transport.

    ``get_object_store`` builds ``SupabaseObjectStore`` by name at call time, so
    swapping the class attribute is enough and no production code is bypassed.
    """
    from app.services.interview import object_store as object_store_module

    class _TransportStubbedStore(SupabaseObjectStore):
        def __init__(self, **kwargs: Any) -> None:
            kwargs.setdefault("transport", httpx.MockTransport(bucket.handler))
            kwargs.setdefault("backoff_seconds", 0.0)
            super().__init__(**kwargs)

    monkeypatch.setattr(object_store_module, "SupabaseObjectStore", _TransportStubbedStore)


@pytest.fixture
def managed(tmp_path, monkeypatch):
    from app import main as main_module
    from app.core.config import get_settings
    from app.db import session as session_module
    from app.services.execution import backend as backend_module
    from app.services.interview import runner as runner_module
    from app.workers import interview_grading as grading_worker

    _configure_env(tmp_path, monkeypatch)
    bucket = StubBucket()
    _stub_supabase_transport(monkeypatch, bucket)

    modal = FakeModal()
    monkeypatch.setitem(sys.modules, "modal", modal)
    get_settings.cache_clear()
    backend_module._modal_backend = None
    runner_module._runner_semaphore = None

    db_file = tmp_path / "managed_workflow.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _create_schema() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(_create_schema())

    async def override_get_db():
        async with factory() as session:
            yield session

    monkeypatch.setattr(session_module, "engine", engine)
    monkeypatch.setattr(session_module, "async_session_factory", factory)
    monkeypatch.setattr(main_module, "engine", engine)
    # ``interview_grading`` bound the factory at import time, so the worker needs
    # the same override to see this test's database.
    monkeypatch.setattr(grading_worker, "async_session_factory", factory)

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    state = SimpleNamespace(
        bucket=bucket,
        modal=modal,
        engine=engine,
        factory=factory,
        workspace_root=Path(tmp_path / "workspaces"),
        settings=get_settings(),
    )
    try:
        with TestClient(app) as client:
            state.client = client
            yield state
    finally:
        app.dependency_overrides.clear()
        backend_module._modal_backend = None
        runner_module._runner_semaphore = None
        asyncio.run(engine.dispose())
        get_settings.cache_clear()


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _signup(client: TestClient, *, email: str, username: str) -> dict:
    response = client.post("/api/auth/signup", json={
        "email": email, "username": username, "password": PASSWORD,
        "first_name": "Beta", "last_name": "User",
    })
    assert response.status_code == 201, response.text
    return response.json()


def _start_session(client: TestClient, slug: str, token: str) -> dict:
    started = client.post("/api/interview/sessions",
                          headers={"Authorization": f"Bearer {token}"},
                          json={"challenge_slug": slug})
    assert started.status_code == 200, started.text
    body = started.json()
    body["headers"] = {"Authorization": f"Bearer {token}", "X-Session-Token": body["owner_token"]}
    return body


def _pick_editable_file(client: TestClient, sid: str, headers: dict) -> str:
    files = client.get(f"/api/interview/sessions/{sid}/files", headers=headers)
    assert files.status_code == 200, files.text
    paths = [entry["path"] if isinstance(entry, dict) else entry for entry in files.json()]
    return next(
        (path for path in paths if path.endswith((".ts", ".tsx", ".js", ".py"))
         and "test" not in path.lower()),
        paths[0],
    )


def _run_grading_worker() -> bool:
    """Drain one durable grading job the way the Modal cron function does."""
    from app.workers.interview_grading import process_one_grading_job

    return asyncio.run(process_one_grading_job())


# --------------------------------------------------------------------------- #
# the workflow
# --------------------------------------------------------------------------- #


def test_managed_stack_full_workflow(managed):
    client, bucket, modal = managed.client, managed.bucket, managed.modal

    challenges = client.get("/api/interview/challenges")
    assert challenges.status_code == 200
    slug = challenges.json()[0]["slug"]

    # signup -> login
    owner = _signup(client, email="managed@example.com", username="managedowner")
    login = client.post("/api/auth/login", json={
        "email": "managed@example.com", "password": PASSWORD,
    })
    assert login.status_code == 200, login.text
    assert login.json()["access_token"]

    # start session
    session = _start_session(client, slug, owner["access_token"])
    sid, headers = session["id"], session["headers"]

    # list + read a starter file
    path = _pick_editable_file(client, sid, headers)
    original = client.get(f"/api/interview/sessions/{sid}/files/{path}", headers=headers)
    assert original.status_code == 200, original.text
    starter_content = original.json()["content"]

    # save an edit
    edit = "\n// managed-integration-edit\n"
    saved = client.put(f"/api/interview/sessions/{sid}/files/{path}",
                       headers=headers, json={"content": starter_content + edit})
    assert saved.status_code == 200, saved.text
    assert saved.json()["content"].endswith("managed-integration-edit\n")

    # ---- run tests: the sandbox path must be the one that executed ----
    modal.created.clear()
    tests = client.post(f"/api/interview/sessions/{sid}/tests",
                        headers=headers, json={"command_id": "run_tests"})
    assert tests.status_code == 200, tests.text
    run = tests.json()
    assert set(run) >= {"ok", "exit_code", "stdout", "stderr", "command", "counts",
                        "isolation", "runner", "advisory", "authoritative", "timed_out"}
    assert run["advisory"] is True and run["authoritative"] is False
    # A Modal sandbox ran the command: not the host, not Docker.
    assert run["isolation"] == "modal", run
    assert run["runner"] == "modal", run
    assert run.get("error_code") is None, run
    assert run["ok"] is True and run["exit_code"] == 0
    assert run["counts"]["passed"] == 1

    assert len(modal.created) == 1, "the advisory run must go through a Modal sandbox"
    sandbox = modal.created[0]
    assert sandbox.terminated is True, "the sandbox must be terminated after the run"
    # The service-owned bootstrap wrapper, with the registered slug and the
    # allowlisted argv, is what the sandbox executed.
    assert sandbox.exec_argv[:2] == ("sh", "-c")
    assert sandbox.exec_argv[3] == "promptcode-modal-bootstrap"
    assert sandbox.exec_argv[4] == slug
    # The validated workspace was uploaded to /source, never mounted from the host.
    assert any(key.startswith("/source/") for key in sandbox.filesystem.files), sandbox.filesystem.files
    assert sandbox.filesystem.files[f"/source/{path}"] == (starter_content + edit).encode()

    kwargs = modal.create_kwargs
    assert kwargs["block_network"] is True, "egress must be blocked on every sandbox"
    assert kwargs["workdir"] == "/workspace"
    assert kwargs["image"].reference in {NODE_IMAGE, PYTHON_IMAGE}
    assert not any("KEY" in name or "SECRET" in name or "TOKEN" in name for name in kwargs["env"])

    # ---- workspace hydration: simulate a fresh container mid-session ----
    from app.models.interview_session import InterviewSession

    async def _recorded_path() -> str:
        async with managed.factory() as db:
            row = await db.get(InterviewSession, uuid.UUID(sid))
            return row.workspace_path

    recorded = Path(asyncio.run(_recorded_path()))
    assert recorded.is_dir(), recorded
    shutil.rmtree(recorded)
    assert not recorded.exists()

    rehydrated = client.get(f"/api/interview/sessions/{sid}/files/{path}", headers=headers)
    assert rehydrated.status_code == 200, rehydrated.text
    assert rehydrated.json()["content"] == starter_content + edit, (
        "a saved edit must survive the loss of the container-local workspace"
    )

    # ---- submit: freeze + durable object upload ----
    submitted = client.post(f"/api/interview/sessions/{sid}/submit", headers=headers, json={})
    assert submitted.status_code == 200, submitted.text
    packet = submitted.json()["assessment"]["packet"]
    digest = packet["source_digest"]
    assert packet["grading_job_id"]
    assert submitted.json()["assessment"]["execution_status"] in {"queued", "running"}

    # The immutable submission is in the private bucket under the provider-neutral
    # key, uploaded through the real authenticated Storage REST path.
    expected_key = f"submitted/{sid}/{digest}/manifest.json"
    assert expected_key in bucket.objects, bucket.keys()
    assert bucket.calls and all(call[2] == f"Bearer {SERVICE_ROLE}" for call in bucket.calls)
    manifest = json.loads(bucket.objects[expected_key].decode())
    assert {row["path"] for row in manifest} >= {path}
    for row in manifest:
        stored = bucket.objects[f"submitted/{sid}/{digest}/{row['path']}"]
        assert hashlib.sha256(stored).hexdigest() == row["sha256"]

    # ---- grading: the durable worker hydrates from the bucket, not from this disk ----
    assert _run_grading_worker() is True
    report = client.get(f"/api/interview/sessions/{sid}/report", headers=headers)
    assert report.status_code == 200, report.text
    assessment = report.json()["assessment"]
    assert assessment["execution_status"] == "completed", assessment
    assert any(item["kind"] == "external_evaluation"
               for item in assessment["packet"]["evidence"]), assessment["packet"]["evidence"]
    # The trusted probes ran in Modal sandboxes too.
    assert any(box.exec_argv and box.exec_argv[0] in {"node", "python"} for box in modal.created)
    assert all(box.terminated for box in modal.created)

    # A second drain finds nothing: the job was completed, not duplicated.
    assert _run_grading_worker() is False


def test_managed_stack_rejects_another_users_session(managed):
    client = managed.client
    slug = client.get("/api/interview/challenges").json()[0]["slug"]

    owner = _signup(client, email="owner2@example.com", username="managedowner2")
    session = _start_session(client, slug, owner["access_token"])
    sid, headers = session["id"], session["headers"]
    path = _pick_editable_file(client, sid, headers)

    intruder = _signup(client, email="intruder@example.com", username="managedintruder")
    intruder_headers = {"Authorization": f"Bearer {intruder['access_token']}"}

    read = client.get(f"/api/interview/sessions/{sid}/files/{path}", headers=intruder_headers)
    assert read.status_code == 404, read.text
    write = client.put(f"/api/interview/sessions/{sid}/files/{path}",
                       headers=intruder_headers, json={"content": "stolen"})
    assert write.status_code == 404, write.text
    files = client.get(f"/api/interview/sessions/{sid}/files", headers=intruder_headers)
    assert files.status_code == 404, files.text
    report = client.get(f"/api/interview/sessions/{sid}/report", headers=intruder_headers)
    assert report.status_code == 404, report.text

    # The owner's own copy is untouched by the rejected write.
    owned = client.get(f"/api/interview/sessions/{sid}/files/{path}", headers=headers)
    assert owned.status_code == 200 and "stolen" not in owned.json()["content"]
