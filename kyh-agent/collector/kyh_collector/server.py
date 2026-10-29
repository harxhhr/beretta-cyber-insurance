"""HTTP(S) API and dashboard server (standard library http.server)."""

from __future__ import annotations

import json
import os
import ssl
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import __version__
from . import core
from . import db as dbm
from . import evaluate as ev
from . import platform_link
from . import settings as settings_mod

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/static/app.js": ("app.js", "application/javascript; charset=utf-8"),
          "/static/style.css": ("style.css", "text/css; charset=utf-8")}


def utcnow():
    return datetime.now(timezone.utc)


class App:
    """Shared state for request handlers: paths, settings, clock, a write lock and a rate limiter."""

    def __init__(self, data_dir: str, clock=utcnow):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.db_path = os.path.join(data_dir, "collector.db")
        dbm.init(self.db_path)
        self.settings = settings_mod.load(data_dir)
        self.clock = clock
        self.lock = threading.Lock()   # serialises ingestion so sequence checks cannot race
        self.hits = defaultdict(deque)
        self.link = platform_link.load_link(data_dir)   # None unless linked to the KYH platform
        self.worker = None

    def start_link_worker(self):
        if self.link and self.worker is None:
            self.worker = platform_link.LinkWorker(self, self.link)
            self.worker.start()

    def conn(self):
        return dbm.connect(self.db_path)

    def rate_limited(self, key: str) -> bool:
        now, q = time.monotonic(), self.hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.settings["rate_limit_per_minute"]:
            return True
        q.append(now)
        return False


class Handler(BaseHTTPRequestHandler):
    server_version = f"KYH-Collector/{__version__}"
    protocol_version = "HTTP/1.1"

    @property
    def app(self) -> App:
        return self.server.app

    def log_message(self, fmt, *args):  # quieter console
        if os.environ.get("KYH_COLLECTOR_VERBOSE"):
            super().log_message(fmt, *args)

    # ------------------------------------------------------------ helpers
    def _send(self, status: int, payload, ctype="application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        if ctype.startswith("text/html"):
            self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, e: core.ApiError):
        self._send(e.status, {"error": e.message, "code": e.code})

    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n > self.app.settings["max_body_bytes"]:
            raise core.ApiError(413, "TOO_LARGE", "request body too large")
        return self.rfile.read(n) if n else b""

    def _admin(self, conn) -> bool:
        auth = self.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else None
        return core.check_admin(conn, token)

    # ------------------------------------------------------------ routes
    def do_POST(self):
        path = urlparse(self.path).path
        try:
            raw = self._body()
            if path == "/api/v1/enroll":
                if self.app.rate_limited("enroll:" + self.client_address[0]):
                    raise core.ApiError(429, "RATE_LIMIT", "too many enrollment attempts")
                with self.app.lock:
                    conn = self.app.conn()
                    try:
                        conn.execute("BEGIN IMMEDIATE")
                        out = core.enroll(conn, self.app.clock(), json.loads(raw or b"{}"))
                        conn.execute("COMMIT")
                    except Exception:
                        conn.execute("ROLLBACK")
                        raise
                    finally:
                        conn.close()
                return self._send(201, out)
            if path == "/api/v1/report":
                agent_id = self.headers.get("X-KYH-Agent-Id", "")
                if self.app.rate_limited("report:" + agent_id):
                    raise core.ApiError(429, "RATE_LIMIT", "too many reports")
                with self.app.lock:
                    conn = self.app.conn()
                    try:
                        now = self.app.clock()
                        conn.execute("BEGIN IMMEDIATE")
                        try:
                            out = core.ingest(conn, now, agent_id, self.headers.get("X-KYH-Signature", ""), raw,
                                              self.app.settings)
                        except core.ApiError:
                            conn.execute("COMMIT")  # keep the audit row for rejected reports
                            raise
                        snap = ev.evaluate_company(conn, out["company_id"], now, self.app.settings)
                        conn.execute("COMMIT")
                    finally:
                        conn.close()
                out["warranty_changes"] = snap.get("warranty_changes", [])
                out["repricing_performed"] = False
                if self.app.worker and snap.get("linked"):
                    self.app.worker.wake.set()   # push the new fleet state to the platform now
                    out["warranty_authority"] = "Beretta platform"
                return self._send(202, out)
            raise core.ApiError(404, "NOT_FOUND", "no such endpoint")
        except core.ApiError as e:
            return self._error(e)
        except (ValueError, KeyError) as e:
            return self._send(400, {"error": f"bad request: {e}", "code": "BAD_REQUEST"})

    def do_GET(self):
        path = urlparse(self.path).path
        if path in STATIC:
            name, ctype = STATIC[path]
            with open(os.path.join(STATIC_DIR, name), "rb") as fh:
                return self._send(200, fh.read(), ctype)
        if path == "/healthz":
            return self._send(200, {"ok": True, "version": __version__})
        if not path.startswith("/api/v1/"):
            return self._send(404, {"error": "not found", "code": "NOT_FOUND"})
        with self.app.lock:
            conn = self.app.conn()
            try:
                if not self._admin(conn):
                    return self._send(401, {"error": "admin token required", "code": "UNAUTHORIZED"})
                now = self.app.clock()
                parts = path.strip("/").split("/")[2:]
                conn.execute("BEGIN IMMEDIATE")
                if parts == ["overview"]:
                    out = []
                    for c in conn.execute("SELECT id FROM companies ORDER BY name").fetchall():
                        snap = ev.evaluate_company(conn, c["id"], now, self.app.settings)
                        out.append({"company": snap["company"], "policy": snap["policy"], "linked": snap.get("linked"),
                                    "coverage": snap["coverage"], "liveness_counts": snap["liveness_counts"],
                                    "warranties": [{"control": w["control"], "state": w["state"]}
                                                   for w in snap["warranties"]]})
                    conn.execute("COMMIT")
                    return self._send(200, {"companies": out, "evaluated_at": core.iso(now)})
                if len(parts) == 2 and parts[0] == "companies":
                    snap = ev.evaluate_company(conn, parts[1], now, self.app.settings)
                    if not snap:
                        conn.execute("ROLLBACK")
                        return self._send(404, {"error": "unknown company", "code": "NOT_FOUND"})
                    snap["events"] = [dict(r) for r in conn.execute(
                        "SELECT * FROM warranty_events WHERE company_id=? ORDER BY id DESC LIMIT 50", (parts[1],))]
                    if snap.get("linked"):
                        controls, skipped = platform_link.build_controls(snap, self.app.settings)
                        snap["platform"].update(
                            url=(self.app.link or {}).get("url"), mapping=controls, unmapped=skipped,
                            control_map=self.app.settings["platform_control_map"])
                    snap["audit"] = [dict(r) for r in conn.execute(
                        "SELECT * FROM audit_log WHERE entity=? OR entity IN (SELECT agent_id FROM agents "
                        "WHERE company_id=?) ORDER BY id DESC LIMIT 50", (parts[1], parts[1]))]
                    conn.execute("COMMIT")
                    return self._send(200, snap)
                if len(parts) == 2 and parts[0] == "agents":
                    detail = ev.host_detail(conn, parts[1])
                    conn.execute("COMMIT")
                    return self._send(200 if detail else 404, detail or {"error": "unknown agent"})
                conn.execute("ROLLBACK")
                return self._send(404, {"error": "not found", "code": "NOT_FOUND"})
            finally:
                conn.close()


def make_server(data_dir: str, host: str = "127.0.0.1", port: int = 8443, tls_cert: str | None = None,
                tls_key: str | None = None, clock=utcnow, start_link: bool = True) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.app = App(data_dir, clock=clock)
    if start_link:
        httpd.app.start_link_worker()
    if tls_cert:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(tls_cert, tls_key)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    return httpd
