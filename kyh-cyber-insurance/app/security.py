"""Authentication, role authorization and basic rate limiting."""
import hmac
import threading
import time

from .database import get_config


class AuthError(Exception):
    def __init__(self, code, message, status=401):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


_rate_lock = threading.Lock()
_rate_buckets = {}  # token -> [window_start, count]


def rate_limit(conn, token):
    limit = get_config(conn, "rate_limit_per_minute") or 240
    now = int(time.time() // 60)
    with _rate_lock:
        window, count = _rate_buckets.get(token, (now, 0))
        if window != now:
            window, count = now, 0
        count += 1
        _rate_buckets[token] = (window, count)
    if count > limit:
        raise AuthError("RATE_LIMITED", "Too many requests; try again shortly.", 429)


def authenticate_user(conn, token):
    if not token:
        raise AuthError("MISSING_TOKEN", "Provide X-Auth-Token header.")
    for row in conn.execute("SELECT * FROM users").fetchall():
        if hmac.compare_digest(row["token"], token):
            rate_limit(conn, token)
            return dict(row)
    raise AuthError("INVALID_TOKEN", "Unknown token.")


def authenticate_agent(conn, token):
    if not token:
        raise AuthError("MISSING_TOKEN", "Agent must send Authorization: Bearer <token>.")
    for row in conn.execute("SELECT * FROM agents").fetchall():
        if hmac.compare_digest(row["token"], token):
            rate_limit(conn, token)
            return dict(row)
    raise AuthError("INVALID_AGENT_TOKEN", "Agent token not recognized.")


ROLE_PERMS = {
    "UNDERWRITER": {"read", "staff", "intake", "quote", "bind", "assess"},
    # The insured customer is read-only, and only for their own company (see api.Handler._own).
    "CUSTOMER": {"read"},
    "ADMIN": {"read", "staff", "intake", "quote", "bind", "assess", "admin"},
}


def require(user, perm):
    if perm not in ROLE_PERMS.get(user["role"], set()):
        raise AuthError("FORBIDDEN", f"Role {user['role']} cannot perform '{perm}'.", 403)


def clean_str(value, field, max_len=200, required=True):
    if value is None or str(value).strip() == "":
        if required:
            raise ValueError(f"{field} is required")
        return None
    s = str(value).strip()
    if len(s) > max_len:
        raise ValueError(f"{field} exceeds {max_len} characters")
    return s


def clean_number(value, field, minimum=None, maximum=None, required=True):
    if value is None:
        if required:
            raise ValueError(f"{field} is required")
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a number")
    if minimum is not None and n < minimum:
        raise ValueError(f"{field} must be >= {minimum}")
    if maximum is not None and n > maximum:
        raise ValueError(f"{field} must be <= {maximum}")
    return n
