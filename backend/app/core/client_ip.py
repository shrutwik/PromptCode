from __future__ import annotations

import ipaddress

from fastapi import Request

from app.core.config import get_settings


def _parse_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def _trusted_networks() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    return tuple(
        ipaddress.ip_network(cidr, strict=False)
        for cidr in get_settings().auth_trusted_proxy_cidrs
    )


def _is_trusted(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
    networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
) -> bool:
    return any(ip in network for network in networks)


def client_ip_from_request(request: Request) -> str:
    """Return the client IP used for rate limits.

    Forwarded headers are ignored unless the immediate peer is a trusted proxy.
    From a trusted proxy, the client is the rightmost address in
    ``X-Forwarded-For`` that is not itself a trusted proxy. That keeps a
    client-supplied leftmost address from choosing the rate-limit key when the
    proxy appends the real client.
    """
    peer_host = request.client.host if request.client and request.client.host else ""
    peer_ip = _parse_ip(peer_host)
    if peer_ip is None:
        return peer_host or "unknown"

    networks = _trusted_networks()
    if not _is_trusted(peer_ip, networks):
        return str(peer_ip)

    forwarded: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for part in request.headers.get("x-forwarded-for", "").split(","):
        parsed = _parse_ip(part)
        if parsed is not None:
            forwarded.append(parsed)
    for ip in reversed(forwarded):
        if not _is_trusted(ip, networks):
            return str(ip)

    real_ip = _parse_ip(request.headers.get("x-real-ip", ""))
    if real_ip is not None and not _is_trusted(real_ip, networks):
        return str(real_ip)
    return str(peer_ip)
