import asyncio
from unittest.mock import MagicMock

from app.services.interview import runner


def test_reaper_preserves_active_and_unlabeled_containers(monkeypatch):
    client = MagicMock()
    containers = []
    for deadline in ('99', '101', '', 'nan', 'invalid'):
        container = MagicMock()
        container.labels = {'promptcode.expires_at': deadline}
        containers.append(container)
    client.containers.list.return_value = containers
    monkeypatch.setattr(runner, '_docker_client', lambda: client)
    monkeypatch.setattr(runner.time, 'time', lambda: 100)
    assert runner.reap_expired_runners() == 1
    containers[0].remove.assert_called_once_with(force=True, v=True)
    for container in containers[1:]: container.remove.assert_not_called()
    assert 'promptcode.expires_at' in client.containers.list.call_args.kwargs['filters']['label']
    client.close.assert_called_once()


def test_lifespan_invokes_reaper_and_disposes_database(monkeypatch):
    from app import main
    from unittest.mock import AsyncMock
    cleanup = MagicMock(return_value=0)
    monkeypatch.setattr(main, 'validate_production_startup', lambda _settings: None)
    monkeypatch.setattr(main, 'runner_mode_safe', lambda: 'docker')
    monkeypatch.setattr(runner, 'reap_expired_runners', cleanup)
    dispose = AsyncMock()
    from types import SimpleNamespace
    monkeypatch.setattr(main, 'engine', SimpleNamespace(dispose=dispose))
    async def exercise():
        async with main.lifespan(main.app):
            cleanup.assert_called_once()
    asyncio.run(exercise())
    dispose.assert_awaited_once()
