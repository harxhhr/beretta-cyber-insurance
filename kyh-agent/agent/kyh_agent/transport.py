"""HTTPS client with certificate pinning to the collector's CA (standard library only)."""

from __future__ import annotations

import ipaddress
import json
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlparse

from . import __version__

LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


def direct_route(host: str | None) -> bool:
    """True for localhost and private/loopback IP literals. A system or corporate proxy cannot reach
    those, so requests to them must not be sent through one (urllib would otherwise use it)."""
    if not host or host == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local


def open_url(req, timeout, context=None):
    host = urllib.request.urlparse(req.full_url).hostname
    if direct_route(host):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                             urllib.request.HTTPSHandler(context=context))
        return opener.open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout, context=context)


class TransportError(Exception):
    """Network-level failure: the report stays in the outbox and is retried later."""


class Transport:
    def __init__(self, server_url: str, ca_file: str | None = None, allow_insecure_http: bool = False,
                 timeout: float = 20):
        u = urlparse(server_url)
        if u.scheme not in ("https", "http"):
            raise ValueError("server_url must be http(s)")
        if u.scheme == "http" and u.hostname not in LOCAL_HOSTS and not allow_insecure_http:
            raise ValueError("Plain HTTP is only allowed to localhost. Use https:// with --ca-file.")
        self.base = server_url.rstrip("/")
        self.timeout = timeout
        self.ctx = None
        if u.scheme == "https":
            # With ca_file, ONLY that CA is trusted (pinning to the KYH collector's private CA).
            self.ctx = ssl.create_default_context(cafile=ca_file) if ca_file else ssl.create_default_context()
            self.ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    def post(self, path: str, body: bytes, headers: dict | None = None):
        req = urllib.request.Request(self.base + path, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", f"kyh-agent/{__version__}")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with open_url(req, self.timeout, self.ctx) as resp:
                return resp.status, _json(resp.read())
        except urllib.error.HTTPError as exc:  # collector answered with an error status
            return exc.code, _json(exc.read())
        except (urllib.error.URLError, OSError, ssl.SSLError) as exc:
            raise TransportError(str(getattr(exc, "reason", exc))) from exc


def _json(raw: bytes):
    try:
        return json.loads(raw.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return {"raw": raw[:200].decode("utf-8", "replace")}
