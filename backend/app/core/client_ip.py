from __future__ import annotations

import ipaddress

from fastapi import Request

from app.core.config import get_settings


def client_ip_from_request(request: Request) -> str:
    """Return the best available client IP, respecting trusted reverse-proxy headers."""
    peer_host = request.client.host if request.client and request.client.host else ""
    try:
        peer_ip = ipaddress.ip_address(peer_host)
    except ValueError:
        peer_ip = None

    if peer_ip is not None:
        trusted_proxy_cidrs = get_settings().auth_trusted_proxy_cidrs
        trusted_proxy_networks = tuple(
            ipaddress.ip_network(cidr, strict=False)
            for cidr in trusted_proxy_cidrs
        )
        if any(peer_ip in network for network in trusted_proxy_networks):
            forwarded_for = request.headers.get("x-forwarded-for", "").strip()
            if forwarded_for:
                for candidate in forwarded_for.split(","):
                    client_ip = candidate.strip()
                    try:
                        return str(ipaddress.ip_address(client_ip))
                    except ValueError:
                        continue
            real_ip = request.headers.get("x-real-ip", "").strip()
            if real_ip:
                try:
                    return str(ipaddress.ip_address(real_ip))
                except ValueError:
                    pass
        return str(peer_ip)

    if peer_host:
        return peer_host
    return "unknown"
