"""Ephemeral-container persistence: workspace hydration and durable submissions.

Ephemeral containers break two assumptions the shared-host deployment got for
free, so this covers both failure modes:

* a lost ``workspace_path`` must rebuild from the challenge starter plus the
  latest revision per path in ``interview_session_files`` (any container can then
  serve the next request), and
* a frozen submission must round-trip through the object store, verify by digest,
  stay idempotent for a repeated digest, and never read back as complete after an
  interrupted upload.

It also pins the grading dispatch fix: a Modal deployment has neither a broker URL
nor a sandbox executor URL, so a claimed job must still reach the in-process
trusted evaluator.
"""
from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.interview_session import InterviewSession, InterviewSessionFile
from app.models.user import User
from app.services.interview import object_store, snapshot, workspace, workspace_store
from app.services.interview.object_store import (
    LocalObjectStore,
    ObjectNotFound,
    ObjectStoreError,
    ObjectTooLarge,
    SupabaseObjectStore,
    manifest_key,
    submission_key,
    submission_prefix,
)
from app.services.interview.snapshot import _manifest, manifest_digest

BUCKET = "promptcode-private"
SERVICE_ROLE = "test-only-service-role-key"
SLUG = "order-hold-reason"
SAVED_PATH = "app/service.py"


def _root_provider(monkeypatch, root: Path) -> Path:
    """Patch the artifact root with the same mkdir-on-demand contract as prod."""
    def root_dir() -> Path:
        root.mkdir(parents=True, exist_ok=True)
        return root

    monkeypatch.setattr(workspace, "workspace_root", root_dir)
    return root


# --- workspace hydration ------------------------------------------------------

async def _seeded_session(tmp_path, *, saved_content: str | None = None):
    """An owned session whose recorded workspace_path belongs to a dead container."""
    engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "sessions.db"))
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(email="hydrate@example.com", username="hydrate", password_hash="test")
        db.add(user)
        await db.flush()
        session = InterviewSession(
            user_id=user.id, owner_token="owned", challenge_slug=SLUG,
            workspace_path=str(tmp_path / "dead-container" / "session"), challenge_version="1",
        )
        db.add(session)
        await db.flush()
        if saved_content is not None:
            db.add(InterviewSessionFile(session_id=session.id, path=SAVED_PATH,
                                        content=saved_content, revision=1))
        await db.commit()
        return engine, factory, session.id


def test_hydration_rebuilds_lost_workspace_from_starter_and_revisions(tmp_path, monkeypatch):
    async def run():
        engine, factory, session_id = await _seeded_session(
            tmp_path, saved_content="# candidate edit\n")
        root = _root_provider(monkeypatch, tmp_path / "container-b")
        async with factory() as db:
            session = await db.get(InterviewSession, session_id)
            rebuilt = await workspace_store.ensure_workspace(db, session)
            assert rebuilt == root / str(session_id)
            # Saved progress wins over the starter copy of that path...
            assert (rebuilt / SAVED_PATH).read_text() == "# candidate edit\n"
            # ...while untouched starter files come from the challenge source.
            assert (rebuilt / "app/main.py").is_file()
            # The immutable starter snapshot is recreated too (diffs need it).
            assert (root / f"{session_id}.starter" / SAVED_PATH).is_file()
            assert (root / f"{session_id}.starter" / SAVED_PATH).read_text() != "# candidate edit\n"
            assert session.workspace_path == str(rebuilt)
            # A materialized workspace is a no-op, so live edits are never clobbered.
            (rebuilt / SAVED_PATH).write_text("# newer live edit\n")
            same = await workspace_store.ensure_workspace(db, session)
            assert same == rebuilt and (rebuilt / SAVED_PATH).read_text() == "# newer live edit\n"
        await engine.dispose()

    asyncio.run(run())


def test_saved_file_survives_a_fresh_container(tmp_path, monkeypatch):
    saved = "def handle():\n    return 'saved'\n"

    async def run():
        engine, factory, session_id = await _seeded_session(tmp_path, saved_content=saved)
        # Container A materializes the workspace, then loses its whole disk.
        root_a = _root_provider(monkeypatch, tmp_path / "container-a")
        async with factory() as db:
            session = await db.get(InterviewSession, session_id)
            first = await workspace_store.ensure_workspace(db, session)
            assert (first / SAVED_PATH).read_text() == saved
            await db.commit()
        shutil.rmtree(root_a)
        # Container B has a different root and must serve the saved bytes.
        root_b = _root_provider(monkeypatch, tmp_path / "container-b")
        async with factory() as db:
            session = await db.get(InterviewSession, session_id)
            assert not Path(session.workspace_path).exists()
            rebuilt = await workspace_store.ensure_workspace(db, session)
            assert rebuilt == root_b / str(session_id)
            assert (rebuilt / SAVED_PATH).read_text() == saved
            assert session.workspace_path == str(rebuilt)
        await engine.dispose()

    asyncio.run(run())


def test_hydration_does_not_replay_frozen_paths(tmp_path, monkeypatch):
    """A stored revision can never restore a runner-owned test file."""
    async def run():
        engine, factory, session_id = await _seeded_session(tmp_path, saved_content="assert True\n")
        async with factory() as db:
            stored = (await db.get(InterviewSession, session_id)).id
            db.add(InterviewSessionFile(session_id=stored, path="tests/test_orders.py",
                                        content="def test_forged(): assert True\n", revision=1))
            await db.commit()
        root = _root_provider(monkeypatch, tmp_path / "container-b")
        async with factory() as db:
            session = await db.get(InterviewSession, session_id)
            rebuilt = await workspace_store.ensure_workspace(db, session)
            assert "test_forged" not in (rebuilt / "tests/test_orders.py").read_text()
            assert rebuilt == root / str(session_id)
        await engine.dispose()

    asyncio.run(run())


# --- durable submissions ------------------------------------------------------

class StubSupabase:
    """In-memory stand-in for the private bucket's object endpoints."""

    def __init__(self, *, fail_on: set[str] | None = None):
        self.objects: dict[str, bytes] = {}
        self.headers: list[str | None] = []
        self.puts = 0
        self.fail_on = fail_on or set()
        self._fail_once: set[str] = set()

    def fail_next_put(self, key: str) -> None:
        self._fail_once.add(key)

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.headers.append(request.headers.get("Authorization"))
        assert path.startswith("/storage/v1/object/"), path
        key = path[len("/storage/v1/object/"):].split("/", 1)[1]
        if request.method == "POST":
            if key in self.fail_on or key in self._fail_once:
                self._fail_once.discard(key)
                return httpx.Response(503, text="unavailable")
            self.objects[key] = request.content
            self.puts += 1
            return httpx.Response(200, json={"Key": key})
        if request.method in {"GET", "HEAD"}:
            if key not in self.objects:
                return httpx.Response(404, json={"statusCode": "404", "error": "not_found"})
            return httpx.Response(200, content=self.objects[key])
        raise AssertionError(f"unexpected request {request.method} {path}")


def stub_store(stub: StubSupabase, **kwargs) -> SupabaseObjectStore:
    kwargs.setdefault("retries", 3)
    kwargs.setdefault("backoff_seconds", 0.0)
    return SupabaseObjectStore(
        base_url="https://stub.supabase.co",
        service_role_key=SERVICE_ROLE,
        bucket=BUCKET,
        timeout=5,
        max_object_bytes=1024 * 1024,
        transport=httpx.MockTransport(stub.handler),
        **kwargs,
    )


class CountingLocalStore(LocalObjectStore):
    """Local store that counts writes so idempotence is observable."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.puts = 0

    def put(self, key: str, data: bytes) -> None:
        super().put(key, data)
        self.puts += 1


def source_tree(root: Path) -> Path:
    (root / "src").mkdir(parents=True)
    (root / "src" / "solution.py").write_text("answer = 42\n")
    (root / "README.md").write_text("ticket\n")
    return root


def persisted_submission(tmp_path, store):
    source = source_tree(tmp_path / "source")
    manifest = _manifest(source)
    digest = manifest_digest(manifest)
    session_id = str(uuid.uuid4())
    prefix = workspace_store.persist_submission(session_id, digest, manifest, source)
    return session_id, digest, manifest, source, prefix


def test_supabase_object_round_trip_uses_private_authenticated_endpoint():
    stub = StubSupabase()
    with stub_store(stub) as store:
        key = submission_key("s1", "a" * 64, "src/solution.py")
        store.put(key, b"answer = 42")
        assert store.get(key) == b"answer = 42"
        assert store.exists(key) is True
        assert store.exists(submission_key("s1", "a" * 64, "src/absent.py")) is False
        with pytest.raises(ObjectNotFound):
            store.get(submission_key("s1", "a" * 64, "src/absent.py"))
        with pytest.raises(ObjectTooLarge):
            store.put(submission_key("s1", "a" * 64, "big.bin"), b"x" * (1024 * 1024 + 1))
    assert all(header == "Bearer " + SERVICE_ROLE for header in stub.headers)
    assert "big.bin" not in "".join(stub.objects)


def test_transient_upload_failure_retries_and_permanent_failure_raises():
    stub = StubSupabase()
    key = submission_key("s1", "a" * 64, "src/solution.py")
    with stub_store(stub) as store:
        stub.fail_next_put(key)
        store.put(key, b"answer = 42")
        assert stub.objects[key] == b"answer = 42"
    failing = StubSupabase(fail_on={key})
    with stub_store(failing, retries=2) as store:
        with pytest.raises(ObjectStoreError):
            store.put(key, b"answer = 42")


def test_submission_round_trips_and_digest_verification_rejects_tampering(tmp_path, monkeypatch):
    store = LocalObjectStore(tmp_path / "objects")
    monkeypatch.setattr(workspace_store, "get_object_store", lambda: store)
    session_id, digest, manifest, _source, _prefix = persisted_submission(tmp_path, store)
    hydrated = workspace_store.fetch_submission(session_id, digest, manifest, tmp_path / "hydrate")
    assert (hydrated / "src" / "solution.py").read_text() == "answer = 42\n"
    # Immutable on disk once materialized.
    assert (hydrated / "src" / "solution.py").stat().st_mode & 0o200 == 0
    store.put(submission_key(session_id, digest, "src/solution.py"), b"answer = 0\n")
    with pytest.raises(ValueError, match="integrity"):
        workspace_store.fetch_submission(session_id, digest, manifest, tmp_path / "hydrate2")
    # A manifest that does not describe the digest it is named by is refused too.
    with pytest.raises(ValueError, match="integrity|digest"):
        workspace_store.fetch_submission(session_id, "b" * 64, manifest, tmp_path / "hydrate3")


def test_repeated_identical_submission_is_idempotent(tmp_path, monkeypatch):
    store = CountingLocalStore(tmp_path / "objects")
    monkeypatch.setattr(workspace_store, "get_object_store", lambda: store)
    source = source_tree(tmp_path / "source")
    manifest = _manifest(source)
    digest = manifest_digest(manifest)
    session_id = str(uuid.uuid4())
    first = workspace_store.persist_submission(session_id, digest, manifest, source)
    assert store.puts == len(manifest) + 1  # file objects plus the commit marker
    keys = sorted(p.relative_to(store.root).as_posix() for p in store.root.rglob("*") if p.is_file())
    before = {key: store.get(key) for key in keys}
    second = workspace_store.persist_submission(session_id, digest, manifest, source)
    assert first == second == submission_prefix(session_id, digest)
    assert store.puts == len(manifest) + 1, "an unchanged digest must not re-upload"
    assert {key: store.get(key) for key in keys} == before
    # A stored digest that no longer verifies is re-uploaded rather than trusted.
    store.put(submission_key(session_id, digest, "src/solution.py"), b"answer = 0\n")
    workspace_store.persist_submission(session_id, digest, manifest, source)
    assert store.get(submission_key(session_id, digest, "src/solution.py")) == b"answer = 42\n"


def test_interrupted_upload_never_reads_back_as_complete(tmp_path, monkeypatch):
    stub = StubSupabase()
    store = stub_store(stub)
    monkeypatch.setattr(workspace_store, "get_object_store", lambda: store)
    source = source_tree(tmp_path / "source")
    manifest = _manifest(source)
    digest = manifest_digest(manifest)
    session_id = str(uuid.uuid4())
    # The connection drops while the commit marker is being written.
    stub.fail_on.add(manifest_key(session_id, digest))
    with pytest.raises(ObjectStoreError):
        workspace_store.persist_submission(session_id, digest, manifest, source)
    assert store.exists(manifest_key(session_id, digest)) is False
    assert store.exists(submission_key(session_id, digest, "src/solution.py")) is True
    with pytest.raises(ValueError, match="not committed"):
        workspace_store.fetch_submission(session_id, digest, [], tmp_path / "hydrate")
    # Completing the upload commits the same content-addressed digest.
    stub.fail_on.clear()
    workspace_store.persist_submission(session_id, digest, manifest, source)
    hydrated = workspace_store.fetch_submission(session_id, digest, manifest, tmp_path / "hydrate")
    assert (hydrated / "src" / "solution.py").read_text() == "answer = 42\n"


# --- grading dispatch ---------------------------------------------------------

def _modal_object_store_settings():
    return SimpleNamespace(
        storage_backend="supabase", execution_backend="modal", execution_broker_url="",
        supabase_url="https://project.supabase.co", supabase_service_role_key=SERVICE_ROLE,
        supabase_storage_bucket=BUCKET, supabase_storage_timeout_seconds=5,
        supabase_max_object_bytes=1024 * 1024,
    )


def test_modal_job_routes_to_in_process_evaluator_without_broker_url(tmp_path, monkeypatch):
    from app.services.interview import trusted_evaluator
    from app.services.interview.calibration import challenge_version_for
    from app.workers import interview_grading as jobs

    store = LocalObjectStore(tmp_path / "objects")
    monkeypatch.setattr(workspace_store, "get_object_store", lambda: store)
    monkeypatch.setattr(object_store, "get_settings", _modal_object_store_settings)
    session_id, digest, manifest, _source, prefix = persisted_submission(tmp_path, store)
    settings = SimpleNamespace(
        storage_backend="supabase", execution_backend="modal", execution_broker_url="",
        sandbox_executor_url="", sandbox_executor_token="",
        grading_signing_key="k" * 32, grading_job_timeout_seconds=5,
    )
    monkeypatch.setattr(jobs, "get_settings", lambda: settings)
    seen: list[Path] = []
    hydrated: list[str] = []

    def evaluate(path, **_kwargs):
        seen.append(Path(path))
        hydrated.append((Path(path) / "src" / "solution.py").read_text())
        return {"payload": "signed"}

    monkeypatch.setattr(trusted_evaluator, "evaluate_snapshot", evaluate)
    job = SimpleNamespace(
        id=uuid.uuid4(), session_id=session_id, source_digest=digest, snapshot_key=prefix,
        # The recorded container-local path is meaningless on this container.
        snapshot_path="/dead-container/interview_workspaces/source",
        snapshot_manifest={"files": manifest}, lease_token="a" * 64,
        challenge_slug=SLUG, challenge_version=challenge_version_for(SLUG),
    )
    assert asyncio.run(jobs._execute(job)) == {"payload": "signed"}
    assert hydrated == ["answer = 42\n"]
    assert seen and "dead-container" not in str(seen[0])
    assert not seen[0].exists()  # the per-attempt temp dir is cleaned up
    # A key that does not belong to this session/digest is refused.
    with pytest.raises(ValueError, match="ownership"):
        asyncio.run(jobs._execute(SimpleNamespace(**{**job.__dict__, "snapshot_key": "submitted/other/x"})))
    # A tampered object never reaches the evaluator.
    store.put(submission_key(session_id, digest, "src/solution.py"), b"answer = 0\n")
    with pytest.raises(ValueError, match="integrity"):
        asyncio.run(jobs._execute(job))


def test_modal_freeze_persists_objects_and_enqueues_the_object_key(tmp_path, monkeypatch):
    """The submit path: freeze uploads to the bucket and the job stores only the key."""
    from app.workers import interview_grading as jobs

    async def run():
        engine, factory, session_id = await _seeded_session(tmp_path)
        store = LocalObjectStore(tmp_path / "objects")
        monkeypatch.setattr(workspace_store, "get_object_store", lambda: store)
        monkeypatch.setattr(object_store, "get_settings", _modal_object_store_settings)
        root = _root_provider(monkeypatch, tmp_path / "container")
        monkeypatch.setattr(snapshot, "workspace_root", lambda: root)
        workspace = root / str(session_id)
        (workspace / "app").mkdir(parents=True)
        (workspace / "app" / "service.py").write_text("answer = 42\n")
        frozen = await asyncio.to_thread(snapshot.freeze_submission, workspace, str(session_id))
        assert frozen.object_key == submission_prefix(str(session_id), frozen.source_digest)
        assert store.exists(manifest_key(str(session_id), frozen.source_digest)) is True
        # The bytes are recoverable from the key alone, on a container with no disk.
        hydrated = await asyncio.to_thread(
            workspace_store.fetch_submission, str(session_id), frozen.source_digest, [], tmp_path / "hydrate")
        assert (hydrated / "app" / "service.py").read_text() == "answer = 42\n"
        async with factory() as db:
            session = await db.get(InterviewSession, session_id)
            job = await jobs.enqueue_grading_job(db, session, frozen)
            await db.commit()
            assert job.snapshot_key == frozen.object_key
            assert job.snapshot_key == submission_prefix(str(session_id), frozen.source_digest)
            assert not job.snapshot_key.startswith("/")
        await engine.dispose()

    asyncio.run(run())


def test_docker_mode_without_broker_or_executor_still_fails_closed(tmp_path, monkeypatch):
    """The Modal branch must not widen the existing docker/executor contract."""
    from app.workers import interview_grading as jobs

    settings = SimpleNamespace(
        storage_backend="filesystem", execution_backend="docker", execution_broker_url="",
        sandbox_executor_url="", sandbox_executor_token="", grading_signing_key="k" * 32,
        grading_job_timeout_seconds=5,
    )
    monkeypatch.setattr(jobs, "get_settings", lambda: settings)
    job = SimpleNamespace(id=uuid.uuid4(), session_id=uuid.uuid4(), source_digest="a" * 64,
                          snapshot_key=None, snapshot_path="/unused", snapshot_manifest={},
                          lease_token="a" * 64, challenge_slug=SLUG, challenge_version="1")
    with pytest.raises(ValueError, match="not configured"):
        asyncio.run(jobs._execute(job))


def test_docker_mode_still_uses_the_owned_host_path(tmp_path, monkeypatch):
    """Filesystem behavior is unchanged: no object store, digest verified in place."""
    from app.services.interview import trusted_evaluator
    from app.services.interview.calibration import challenge_version_for
    from app.workers import interview_grading as jobs

    monkeypatch.setattr(object_store, "get_settings", lambda: SimpleNamespace(
        storage_backend="filesystem", execution_backend="docker", execution_broker_url=""))
    monkeypatch.setattr(snapshot, "workspace_root", lambda: tmp_path)
    monkeypatch.setattr(workspace, "workspace_root", lambda: tmp_path)
    session_id = str(uuid.uuid4())
    source = tmp_path / session_id
    source.mkdir()
    (source / "src").mkdir()
    (source / "src" / "solution.py").write_text("answer = 42\n")
    frozen = snapshot.freeze_submission(source, session_id)
    assert frozen.object_key == submission_prefix(session_id, frozen.source_digest)
    settings = SimpleNamespace(
        storage_backend="filesystem", execution_backend="docker",
        execution_broker_url="https://broker", grading_signing_key="k" * 32,
        grading_job_timeout_seconds=5,
    )
    monkeypatch.setattr(jobs, "get_settings", lambda: settings)
    seen: list[Path] = []
    monkeypatch.setattr(trusted_evaluator, "evaluate_snapshot",
                        lambda path, **_kw: seen.append(Path(path)) or {"payload": "signed"})
    job = SimpleNamespace(
        id=uuid.uuid4(), session_id=session_id, source_digest=frozen.source_digest,
        snapshot_key=frozen.object_key, snapshot_path=str(frozen.source_path),
        snapshot_manifest={"files": frozen.manifest}, lease_token="a" * 64,
        challenge_slug=SLUG, challenge_version=challenge_version_for(SLUG),
    )
    assert asyncio.run(jobs._execute(job)) == {"payload": "signed"}
    assert seen == [frozen.source_path]
    # Ownership is still enforced against the host root.
    with pytest.raises(ValueError, match="ownership"):
        asyncio.run(jobs._execute(SimpleNamespace(**{**job.__dict__, "snapshot_path": "/etc"})))
