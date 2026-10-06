"""Exercise candidate-facing relay body and connection limits on loopback."""
import socket
import time

import pytest

from app.services.sandbox.relay import SandboxLLMBudget, SandboxLLMRelay


def relay():
    return SandboxLLMRelay(api_key="unused", base_url="https://api.deepseek.com", host_alias="localhost",
        budget=SandboxLLMBudget(("deepseek-flash",), 2, 20000, 600, 12000, .20),
        request_sender=lambda _payload: pytest.fail("Invalid transport reached a paid provider"))


@pytest.mark.parametrize("extra", ["Content-Length: 999999999", "Content-Length: -1",
                                  "Content-Length: 20\r\nTransfer-Encoding: chunked"])
def test_relay_rejects_body_before_reading(monkeypatch, extra):
    with relay() as service, socket.create_connection(("127.0.0.1", service.port), timeout=2) as connection:
        connection.sendall(("POST /v1/llm/call HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer "
            + service.token + "\r\n" + extra + "\r\n\r\n").encode())
        response = connection.recv(4096)
        assert b"413" in response or b"400" in response


def test_relay_limits_blocked_candidate_connections():
    connections = []
    with relay() as service:
        try:
            for _ in range(8):
                connection = socket.create_connection(("127.0.0.1", service.port), timeout=2)
                connections.append(connection)
                connection.sendall(b"POST /v1/llm/call HTTP/1.1\r\n")
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and service._server._request_slots._value:
                time.sleep(.01)
            assert service._server._request_slots._value == 0
            with socket.create_connection(("127.0.0.1", service.port), timeout=2) as extra:
                extra.settimeout(2)
                assert extra.recv(1) == b""
        finally:
            for connection in connections:
                connection.close()
