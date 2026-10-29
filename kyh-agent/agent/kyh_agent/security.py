"""Report signing and agent self-integrity."""

from __future__ import annotations

import hashlib
import hmac
import os

SIG_PREFIX = "v1="


def sign(secret_hex: str, body: bytes) -> str:
    """HMAC-SHA256 over the exact bytes sent. The collector recomputes it with its copy of the secret."""
    return SIG_PREFIX + hmac.new(bytes.fromhex(secret_hex), body, hashlib.sha256).hexdigest()


def verify(secret_hex: str, body: bytes, header: str) -> bool:
    if not header or not header.startswith(SIG_PREFIX):
        return False
    return hmac.compare_digest(sign(secret_hex, body), header)


def build_hash(package_dir: str | None = None) -> str:
    """SHA-256 over every .py file and the policy in the agent package, in sorted path order.

    The collector keeps a list of approved release hashes. A modified agent produces a
    different hash, so its reports are stored but not trusted as TECHNICALLY_OBSERVED.
    """
    package_dir = package_dir or os.path.dirname(os.path.abspath(__file__))
    h = hashlib.sha256()
    files = []
    for root, dirs, names in os.walk(package_dir):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for n in names:
            if n.endswith(".py") or n == "policy.json":
                files.append(os.path.join(root, n))
    for path in sorted(files, key=lambda p: os.path.relpath(p, package_dir).replace(os.sep, "/")):
        rel = os.path.relpath(path, package_dir).replace(os.sep, "/")
        h.update(rel.encode() + b"\0")
        with open(path, "rb") as fh:
            h.update(fh.read().replace(b"\r\n", b"\n"))
        h.update(b"\0")
    return h.hexdigest()
