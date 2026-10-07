from types import SimpleNamespace

import httpx
import pytest

from scripts import check_deepseek


def test_setup_check_only_uses_unpaid_get_requests(monkeypatch, capsys):
    monkeypatch.setattr(check_deepseek, 'get_settings', lambda: SimpleNamespace(deepseek_api_key='test-only-key'))
    requests = []
    def respond(request):
        requests.append(request)
        assert request.method == 'GET'
        if request.url.path == '/user/balance':
            return httpx.Response(200, json={'is_available': True})
        return httpx.Response(200, json={'data': [{'id': 'deepseek-flash'}]})
    original = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    assert check_deepseek.main() == 0
    assert len(requests) == 2
    assert 'test-only-key' not in capsys.readouterr().out


@pytest.mark.parametrize('key', ['', 'invalid-key'])
def test_setup_check_missing_or_invalid_key_is_safe(monkeypatch, capsys, key):
    monkeypatch.setattr(check_deepseek, 'get_settings', lambda: SimpleNamespace(deepseek_api_key=key))
    original = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: original(transport=httpx.MockTransport(lambda request: httpx.Response(401, text='invalid-key')), **kwargs))
    assert check_deepseek.main() == 1
    assert 'invalid-key' not in capsys.readouterr().out
