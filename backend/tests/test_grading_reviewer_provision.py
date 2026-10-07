"""Operator provisioning changes the existing account and records its audit trail."""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.beta_ops import ProductAnalyticsEvent
from app.models.user import User
from scripts import manage_grading_reviewer as provisioner


@pytest.mark.asyncio
async def test_existing_email_normalization_grant_revoke_and_audit(tmp_path, monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "reviewers.db"))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(provisioner, "async_session_factory", factory)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as db:
            user = User(email="reviewer@example.com", username="reviewer", password_hash="test-only",
                        role="candidate")
            db.add(user)
            await db.commit()
            identity = user.id
        assert await provisioner.provision("  REVIEWER@EXAMPLE.COM ", True) is True
        async with factory() as db:
            assert (await db.get(User, identity)).role == "interviewer"
        assert await provisioner.provision("REVIEWER@example.com", False) is True
        async with factory() as db:
            assert (await db.get(User, identity)).role == "candidate"
            events = (await db.execute(select(ProductAnalyticsEvent).where(
                ProductAnalyticsEvent.event_name == "grading_reviewer_role_changed"))).scalars().all()
            assert len(events) == 2
            assert all(event.user_id == identity for event in events)
            assert {event.properties["role"] for event in events} == {"interviewer", "candidate"}
            assert all(event.properties["source"] == "server_operator_cli" for event in events)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_unknown_account_is_not_created_or_audited(tmp_path, monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "unknown.db"))
    factory = async_sessionmaker(engine)
    monkeypatch.setattr(provisioner, "async_session_factory", factory)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        assert await provisioner.provision("missing@example.com", True) is False
        async with factory() as db:
            assert (await db.execute(select(User))).scalars().all() == []
            assert (await db.execute(select(ProductAnalyticsEvent))).scalars().all() == []
    finally:
        await engine.dispose()
