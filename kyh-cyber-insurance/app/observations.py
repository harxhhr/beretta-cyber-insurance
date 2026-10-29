"""Engine A — Information Gathering.

Every source writes immutable rows into `observations`. Resolution answers
"what is the current best-evidenced state of each control, and where did
that value come from?"
"""
import json

from . import audit, catalogue
from .database import new_id, now_iso

_STRENGTH_RANK = {s: i for i, s in enumerate(catalogue.EVIDENCE_STRENGTHS)}
VALID_VALUES = {"true", "false", "partial"}


class ValidationError(Exception):
    def __init__(self, code, message, field=None):
        super().__init__(message)
        self.code, self.message, self.field = code, message, field


def record_observation(conn, company_id, control_id, value, source_type,
                       source_id=None, source_locator=None, evidence_strength=None,
                       confidence=1.0, dims=None, observed_at=None, notes=None,
                       actor="system"):
    """Append one observation. Observations are never updated in place —
    corrections are new rows (history is preserved)."""
    value = str(value).lower()
    if value in ("1", "yes", "pass"):
        value = "true"
    if value in ("0", "no", "fail"):
        value = "false"
    if value not in VALID_VALUES:
        raise ValidationError("INVALID_CONTROL_VALUE",
                              "Expected boolean value (true/false/partial)", control_id)
    if source_type not in catalogue.SOURCE_TYPES:
        raise ValidationError("INVALID_SOURCE_TYPE", f"Unknown source type {source_type}")
    ctrl = conn.execute("SELECT control_id FROM controls WHERE control_id=?",
                        (control_id,)).fetchone()
    if not ctrl:
        raise ValidationError("UNKNOWN_CONTROL", f"Unknown control {control_id}", control_id)
    strength = evidence_strength or catalogue.SOURCE_DEFAULT_EVIDENCE[source_type]
    if strength not in _STRENGTH_RANK:
        raise ValidationError("INVALID_EVIDENCE_STRENGTH", f"Unknown strength {strength}")
    # Existence vs currency vs tested: an untested/stale artefact cannot carry
    # TESTED strength, and dims themselves can downgrade the value.
    if dims is not None:
        if not isinstance(dims, dict):
            raise ValidationError("INVALID_DIMS", "dims must be an object")
        if dims.get("tested") is False and strength == "TESTED":
            strength = "DOCUMENTED"
        if dims.get("current") is False and value == "true":
            value = "partial"
        if dims.get("exists") is False:
            value = "false"
    oid = new_id("OBS")
    ts = observed_at or now_iso()
    conn.execute("""INSERT INTO observations
        (observation_id,company_id,control_id,value,dims,source_type,source_id,
         observed_at,received_at,source_locator,evidence_strength,confidence,status,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'ACTIVE', ?)""",
        (oid, company_id, control_id, value,
         json.dumps(dims) if dims else None, source_type, source_id, ts, now_iso(),
         source_locator, strength, float(confidence), notes))
    audit.log(conn, actor=actor, event_type="CONTROL_OBSERVATION_CREATED",
              entity_type="OBSERVATION", entity_id=oid,
              new_value={"company_id": company_id, "control_id": control_id,
                         "value": value, "source_type": source_type,
                         "evidence_strength": strength,
                         "source_locator": source_locator})
    return oid


def resolve_posture(conn, company_id):
    """For each control (15 priced + monitoring-only) pick the current best observation:
    highest evidence strength wins; ties broken by most recent observed_at.
    Returns {control_id: resolved dict} with provenance and conflict flags."""
    controls = conn.execute("SELECT * FROM controls ORDER BY tier, control_id").fetchall()
    posture = {}
    for c in controls:
        rows = conn.execute("""SELECT rowid AS _rid, * FROM observations
                               WHERE company_id=? AND control_id=? AND status='ACTIVE'
                               ORDER BY observed_at DESC, _rid DESC""",
                            (company_id, c["control_id"])).fetchall()
        if not rows:
            posture[c["control_id"]] = dict(
                control_id=c["control_id"], name=c["name"], tier=c["tier"],
                is_warranty=bool(c["is_warranty"]), monitoring_only=bool(c["monitoring_only"]),
                status="UNKNOWN", value=None,
                evidence_strength=None, source_type=None, source_locator=None,
                observation_id=None, observed_at=None, dims=None, conflict=False,
                sources=[])
            continue
        best = max(rows, key=lambda r: (_STRENGTH_RANK[r["evidence_strength"]],
                                        r["observed_at"], r["received_at"], r["_rid"]))
        values = {r["value"] for r in rows}
        posture[c["control_id"]] = dict(
            control_id=c["control_id"], name=c["name"], tier=c["tier"],
            is_warranty=bool(c["is_warranty"]), monitoring_only=bool(c["monitoring_only"]),
            status={"true": "PASS", "false": "FAIL", "partial": "PARTIAL"}[best["value"]],
            value=best["value"], evidence_strength=best["evidence_strength"],
            source_type=best["source_type"], source_locator=best["source_locator"],
            observation_id=best["observation_id"], observed_at=best["observed_at"],
            dims=json.loads(best["dims"]) if best["dims"] else None,
            conflict=len(values) > 1,
            sources=[dict(observation_id=r["observation_id"], value=r["value"],
                          source_type=r["source_type"], source_locator=r["source_locator"],
                          evidence_strength=r["evidence_strength"],
                          observed_at=r["observed_at"], notes=r["notes"]) for r in rows])
    return posture


# Outside-in scan findings are evidence for a control (pricing V2 has no separate exposure modifier).
# signal type -> (control, value). An explicit related control on the signal wins; its value is "false"
# for an adverse finding.
SIGNAL_EVIDENCE = {
    "EXPOSED_RDP": ("CTRL-SECCONFIG", "false"),
    "EXPOSED_SMB": ("CTRL-SECCONFIG", "false"),
    "TLS_WEAK": ("CTRL-SECCONFIG", "false"),
    "EOL_SOFTWARE": ("CTRL-SECCONFIG", "false"),
    "UNPATCHED_CRITICAL_CVE": ("CTRL-PATCH-CRIT", "false"),
    "DMARC_MISSING": ("CTRL-EMAILSEC", "false"),
    "DMARC_PRESENT": ("CTRL-EMAILSEC", "true"),
}


def record_signal(conn, company_id, signal_type, detail=None, related_control_id=None, actor="system"):
    """Store an imported outside-in signal and, where it speaks to a control, the observation it implies."""
    signal_type = str(signal_type).strip().upper()
    mapped = SIGNAL_EVIDENCE.get(signal_type)
    control, value = (related_control_id, "false") if related_control_id else (mapped or (None, None))
    severity = "POSITIVE" if value == "true" else "ADVERSE"
    sid = new_id("SIG")
    ts = now_iso()
    conn.execute("INSERT INTO outside_in_signals VALUES (?,?,?,?,?,?,?,?)",
                 (sid, company_id, signal_type, detail, severity, control, ts, ts))
    audit.log(conn, actor=actor, event_type="OUTSIDE_IN_SIGNAL_RECORDED", entity_type="SIGNAL", entity_id=sid,
              new_value={"company_id": company_id, "signal_type": signal_type, "related_control_id": control})
    oid = None
    if control:
        oid = record_observation(conn, company_id, control, value, source_type="OUTSIDE_IN_SCAN", source_id=sid,
                                 source_locator=f"Outside-in signal {signal_type}", notes=detail, actor=actor)
    return sid, oid


DOCUMENT_CATEGORIES = {
    "CAIQ": ("STANDARDIZED_QUESTIONNAIRE", "DOCUMENTED"),
    "SIG_LITE": ("STANDARDIZED_QUESTIONNAIRE", "DOCUMENTED"),
    "SOC2_TYPE2": ("AUDIT_ARTIFACT", "DOCUMENTED"),
    "ISO27001_SOA": ("AUDIT_ARTIFACT", "DOCUMENTED"),
    "VAPT_REPORT": ("AUDIT_ARTIFACT", "DOCUMENTED"),
    "SCAN_EXPORT": ("TECHNICAL_ARTIFACT", "DOCUMENTED"),
    "CONFIG_REPORT": ("TECHNICAL_ARTIFACT", "DOCUMENTED"),
    "ENDPOINT_REPORT": ("TECHNICAL_ARTIFACT", "DOCUMENTED"),
    "IDP_MFA_EXPORT": ("TECHNICAL_ARTIFACT", "DOCUMENTED"),   # identity-provider MFA enforcement export
    "BACKUP_TEST_REPORT": ("TESTING_EVIDENCE", "TESTED"),
    "IR_EXERCISE_EVIDENCE": ("TESTING_EVIDENCE", "TESTED"),
    "PENTEST_EVIDENCE": ("TESTING_EVIDENCE", "TESTED"),
    "NARRATIVE_POLICY": ("NARRATIVE", "DECLARED"),
    "SECURITY_DESCRIPTION": ("NARRATIVE", "DECLARED"),
}


def register_document(conn, company_id, document_type, filename, actor):
    """Documents are metadata + assessed fields; uploads are never executed and
    the prototype does not pretend to run AI extraction — assessed fields are
    entered through a transparent workflow with locators."""
    if document_type not in DOCUMENT_CATEGORIES:
        raise ValidationError("INVALID_DOCUMENT_TYPE",
                              f"Unsupported document_type {document_type}", "document_type")
    safe_name = "".join(ch for ch in filename if ch.isalnum() or ch in "._- ")[:120] or "document"
    category, strength = DOCUMENT_CATEGORIES[document_type]
    did = new_id("DOC")
    conn.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?)",
                 (did, company_id, document_type, category, safe_name, now_iso(),
                  "PENDING", strength))
    audit.log(conn, actor=actor, event_type="DOCUMENT_UPLOADED", entity_type="DOCUMENT",
              entity_id=did, new_value={"company_id": company_id,
                                        "document_type": document_type,
                                        "filename": safe_name, "category": category})
    return did


def assess_document_field(conn, document_id, control_id, value, source_locator,
                          dims=None, evidence_strength=None, actor="underwriter"):
    doc = conn.execute("SELECT * FROM documents WHERE document_id=?", (document_id,)).fetchone()
    if not doc:
        raise ValidationError("UNKNOWN_DOCUMENT", f"No document {document_id}")
    if not source_locator:
        raise ValidationError("MISSING_SOURCE_LOCATOR",
                              "Every extracted value needs a source locator", "source_locator")
    strength = evidence_strength or doc["default_evidence_strength"]
    oid = record_observation(conn, company_id=doc["company_id"], control_id=control_id,
                             value=value, source_type="DOCUMENT", source_id=document_id,
                             source_locator=source_locator, evidence_strength=strength,
                             dims=dims, actor=actor)
    conn.execute("UPDATE documents SET assessment_status='ASSESSED' WHERE document_id=?",
                 (document_id,))
    return oid
