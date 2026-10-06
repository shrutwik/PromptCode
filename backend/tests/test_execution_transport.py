import asyncio
from types import SimpleNamespace

import httpx
import pytest

from app.core.execution_transport import broker_json, broker_json_async, broker_tls_context


def test_sync_broker_response_stops_reading_and_closes_on_limit():
    class Stream(httpx.SyncByteStream):
        reads = 0
        closed = False
        def __iter__(self):
            for _ in range(100):
                self.reads += 1
                yield b"x" * 65536
        def close(self):
            self.closed = True
    stream = Stream()
    with httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200, stream=stream))) as client:
        with pytest.raises(ValueError, match="exceeds limit"):
            broker_json(client, "GET", "https://execution.example.com", max_bytes=1000)
    assert stream.reads == 1 and stream.closed


def test_broker_rejects_compression_before_decompression():
    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            pytest.fail("Compressed execution reply was read")
            yield b""
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, headers={"Content-Encoding": "gzip"}, stream=Stream()))
    with httpx.Client(transport=transport) as client, pytest.raises(ValueError, match="Compressed"):
        broker_json(client, "GET", "https://execution.example.com")


def test_async_broker_response_is_bounded_and_closed():
    class Stream(httpx.AsyncByteStream):
        closed = False
        async def __aiter__(self):
            yield b"x" * 65536
            pytest.fail("Oversized execution reply continued reading")
        async def aclose(self):
            self.closed = True
    stream = Stream()
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(200, stream=stream))) as client:
            with pytest.raises(ValueError, match="exceeds limit"):
                await broker_json_async(client, "GET", "https://execution.example.com", max_bytes=1000)
    asyncio.run(exercise())
    assert stream.closed


def test_missing_private_ca_never_falls_back_to_unverified_tls(tmp_path):
    with pytest.raises(OSError):
        broker_tls_context(SimpleNamespace(execution_broker_ca_file=str(tmp_path / "missing.pem")))
