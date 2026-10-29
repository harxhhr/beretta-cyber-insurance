"""Audit trail. Append-only; every important action calls audit.log()."""
import json

from .database import new_id, now_iso


def log(conn, actor, event_type, entity_type=None, entity_id=None,
        old_value=None, new_value=None, metadata=None):
    eid = new_id("EVT")
    conn.execute(
        "INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?,?)",
        (eid, now_iso(), actor, event_type, entity_type, entity_id,
         json.dumps(old_value) if old_value is not None else None,
         json.dumps(new_value) if new_value is not None else None,
         json.dumps(metadata) if metadata is not None else None))
    return eid


def query(conn, event_type=None, entity_id=None, actor=None, limit=200):
    sql = "SELECT * FROM audit_events WHERE 1=1"
    args = []
    if event_type:
        sql += " AND event_type=?"; args.append(event_type)
    if entity_id:
        sql += " AND entity_id=?"; args.append(entity_id)
    if actor:
        sql += " AND actor=?"; args.append(actor)
    sql += " ORDER BY timestamp DESC, event_id DESC LIMIT ?"
    args.append(min(int(limit), 1000))
    rows = conn.execute(sql, args).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("old_value", "new_value", "metadata"):
            if d.get(k):
                try:
                    d[k] = json.loads(d[k])
                except ValueError:
                    pass
        out.append(d)
    return out
