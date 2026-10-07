"""TLS verification for the private execution management connection."""
import json
import ssl
from typing import Any

import httpx

from app.core.config import Settings


def broker_tls_context(settings: Settings) -> ssl.SSLContext | bool:
    ca_file = str(getattr(settings, "execution_broker_ca_file", "") or "").strip()
    return ssl.create_default_context(cafile=ca_file) if ca_file else True


def broker_json(client: httpx.Client, method: str, url: str, *, max_bytes: int = 1024 * 1024, **kwargs: Any) -> Any:
    """Cap decompressed bytes before parsing an untrusted execution-host reply."""
    with client.stream(method, url, **kwargs) as response:
        response.raise_for_status()
        if response.headers.get("content-encoding", "identity").lower() != "identity":
            raise ValueError("Compressed execution broker responses are unsupported")
        body = bytearray()
        for chunk in response.iter_bytes(chunk_size=65536):
            body.extend(chunk)
            if len(body) > max_bytes:
                raise ValueError("Execution broker response exceeds limit")
        return json.loads(body)


async def broker_json_async(client: httpx.AsyncClient, method: str, url: str, *, max_bytes: int = 1024 * 1024, **kwargs: Any) -> Any:
    async with client.stream(method, url, **kwargs) as response:
        response.raise_for_status()
        if response.headers.get("content-encoding", "identity").lower() != "identity":
            raise ValueError("Compressed execution broker responses are unsupported")
        body = bytearray()
        async for chunk in response.aiter_bytes(chunk_size=65536):
            body.extend(chunk)
            if len(body) > max_bytes:
                raise ValueError("Execution broker response exceeds limit")
        return json.loads(body)
