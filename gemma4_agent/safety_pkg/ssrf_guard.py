"""SSRF protection helpers for outbound HTTP from tool handlers.

Pulled out of :mod:`gemma4_agent.tools` in Sprint 5b. Pure stdlib;
no internal dependencies. ``_http_get_text`` in tools still uses both
names — they are re-exported from there so existing callers keep
working.

T2-web-no-redirect-cap-014: refuse requests that target private /
loopback / link-local / reserved / multicast addresses, and refuse
redirects that resolve to such hosts after the initial check.
"""
from __future__ import annotations

import ipaddress
import socket
import urllib.error
import urllib.request


def _is_private_host(host: str) -> bool:
    """T2-web-no-redirect-cap-014: rechaza loopback/RFC1918/link-local."""
    if not host:
        return False
    host_norm = host.split(":", 1)[0].strip("[]")
    if host_norm.lower() in {"localhost", "ip6-localhost", "ip6-loopback"}:
        return True
    # Si es IP literal, comprobamos directamente.
    try:
        ip = ipaddress.ip_address(host_norm)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
    except ValueError:
        pass
    # Si es hostname, resolvemos y comprobamos cada IP.
    try:
        infos = socket.getaddrinfo(host_norm, None)
    except socket.gaierror:
        return False
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except (ValueError, IndexError):
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
    return False


class _SSRFGuardRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Cap redirect count and re-validate each redirect target host."""

    max_redirections = 5

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        from urllib.parse import urlparse
        host = urlparse(newurl).hostname or ""
        if _is_private_host(host):
            raise urllib.error.HTTPError(newurl, 451, f"refused redirect to private host: {host}", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


__all__ = ["_is_private_host", "_SSRFGuardRedirectHandler"]
