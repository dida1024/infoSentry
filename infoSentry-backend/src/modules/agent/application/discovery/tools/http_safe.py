"""Shared SSRF-safe HTTP utilities for discovery tools."""

from __future__ import annotations

import socket
from ipaddress import ip_address
from urllib.parse import urlparse

import httpx
from loguru import logger

from src.core.infrastructure.logging import get_business_logger

MAX_REDIRECTS = 5


def _is_blocked_ip(value: str) -> bool:
    ip_val = ip_address(value)
    return (
        ip_val.is_private
        or ip_val.is_loopback
        or ip_val.is_link_local
        or ip_val.is_reserved
        or ip_val.is_multicast
    )


def is_allowed_url(url: str) -> bool:
    """SSRF validation — block private IPs, localhost, reserved ranges."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname
    if not host:
        return False
    if host in {"localhost"}:
        return False
    if host.endswith((".local", ".internal")):
        return False
    try:
        return not _is_blocked_ip(host)
    except ValueError:
        pass

    try:
        addr_infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return True

    resolved_ips = {str(info[4][0]) for info in addr_infos if info[4]}
    if not resolved_ips:
        return True

    return all(not _is_blocked_ip(ip) for ip in resolved_ips)


async def safe_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    timeout: float = 10.0,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """HTTP GET with redirect-safe SSRF validation.

    Disables automatic redirects and validates each hop against SSRF rules.
    Raises httpx.HTTPError or ValueError on blocked redirect.
    """
    current_url = url
    for _ in range(MAX_REDIRECTS):
        if not is_allowed_url(current_url):
            msg = f"SSRF blocked: {current_url}"
            get_business_logger().warning(
                "discovery_ssrf_blocked",
                url=current_url,
            )
            raise ValueError(msg)

        resp = await client.get(
            current_url,
            timeout=timeout,
            follow_redirects=False,
            headers=headers,
        )

        if resp.is_redirect:
            location = resp.headers.get("location", "")
            if not location:
                return resp
            # Resolve relative redirects
            if not location.startswith(("http://", "https://")):
                from urllib.parse import urljoin
                location = urljoin(current_url, location)
            logger.debug(f"Redirect {current_url} -> {location}")
            current_url = location
            continue

        return resp

    msg = f"Too many redirects from {url}"
    raise httpx.TooManyRedirects(msg)
