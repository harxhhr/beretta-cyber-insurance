"""Offline outbox. Every report is written here first, then sent. If the collector is
unreachable, reports wait here (in order, with their original timestamps and sequence
numbers) and are replayed when the connection returns."""

from __future__ import annotations

import os
import sqlite3
import threading

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS outbox (
    seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, created_at TEXT NOT NULL, body BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS dead_letter (
    seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, created_at TEXT NOT NULL, body BLOB NOT NULL,
    http_status INTEGER, reason TEXT
);
"""


class Spool:
    def __init__(self, path: str, max_rows: int = 10000):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.path = path
        self.max_rows = max_rows
        self._lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.executescript(SCHEMA)

    def next_seq(self) -> int:
        """Monotonic sequence number that survives restarts (the collector rejects any seq it has seen)."""
        with self._lock:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT v FROM meta WHERE k='seq'").fetchone()
            seq = (int(row[0]) if row else 0) + 1
            self.db.execute("INSERT OR REPLACE INTO meta (k, v) VALUES ('seq', ?)", (str(seq),))
            self.db.execute("COMMIT")
            return seq

    def put(self, seq: int, kind: str, created_at: str, body: bytes) -> None:
        with self._lock:
            self.db.execute("INSERT INTO outbox (seq, kind, created_at, body) VALUES (?,?,?,?)",
                            (seq, kind, created_at, body))
            self._enforce_cap()

    def _enforce_cap(self) -> None:
        n = self.db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
        excess = n - self.max_rows
        # Drop the least valuable first: old heartbeats, then old deltas. Full snapshots are kept longest.
        for kind in ("heartbeat", "delta", "full"):
            if excess <= 0:
                break
            cur = self.db.execute(
                "DELETE FROM outbox WHERE seq IN (SELECT seq FROM outbox WHERE kind=? ORDER BY seq LIMIT ?)",
                (kind, excess))
            excess -= cur.rowcount

    def pending(self, limit: int = 50) -> list:
        with self._lock:
            return self.db.execute("SELECT seq, kind, created_at, body FROM outbox ORDER BY seq LIMIT ?",
                                   (limit,)).fetchall()

    def ack(self, seq: int) -> None:
        with self._lock:
            self.db.execute("DELETE FROM outbox WHERE seq=?", (seq,))

    def dead_letter(self, seq: int, http_status: int, reason: str) -> None:
        with self._lock:
            row = self.db.execute("SELECT seq, kind, created_at, body FROM outbox WHERE seq=?", (seq,)).fetchone()
            if row:
                self.db.execute("INSERT OR REPLACE INTO dead_letter VALUES (?,?,?,?,?,?)",
                                (*row, http_status, reason[:500]))
                self.db.execute("DELETE FROM outbox WHERE seq=?", (seq,))

    def depth(self) -> int:
        with self._lock:
            return self.db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]

    def close(self) -> None:
        self.db.close()
