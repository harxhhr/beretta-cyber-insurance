# API reference

All endpoints return JSON. User endpoints require `X-Auth-Token` (role tokens in
`data/secrets.json`); the agent endpoint requires `Authorization: Bearer <agent token>`.
Errors are structured: `{"error": CODE, "message": ..., "field"?: ...}`.

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | /api/meta | — | Controls, sectors, evidence/source enums, disclaimer |
| GET | /api/demo/tokens | — | PROTOTYPE ONLY: demo role tokens for the local UI |
| GET | /api/dashboard | any | Portfolio stats + recent audit |
| GET/POST | /api/companies | any / intake | List / onboard (creates policy + agent token) |
| GET | /api/companies/{id} | any | Full company detail (policy, docs, claims, signals, calcs, agent) |
| GET | /api/posture/{id} | any | Resolved 15-control posture with provenance |
| POST | /api/questionnaires | intake | Record DECLARED answers (with dims/notes) |
| GET | /api/questionnaires/{company_id} | any | Questionnaire-source observations |
| POST | /api/documents | intake | Register document metadata (never executed) |
| POST | /api/documents/{id}/assess | assess | Record an extracted field (locator required) |
| GET | /api/documents/{company_id} | any | Documents for a company |
| POST/GET | /api/claims, /api/claims/{company_id} | intake/any | Claims history |
| POST/GET | /api/outside-in, /api/outside-in/{company_id} | intake/any | Outside-in signals |
| POST | /api/agent/report | agent | Ingest report → observations → warranty eval if bound. Never re-prices. |
| GET | /api/agent/status/{company_id} | any | Connected, last seen, endpoint count, latest report |
| POST | /api/quote | quote | Calculate + persist premium (409 POLICY_ALREADY_BOUND if bound) |
| GET | /api/quote/{calculation_id} | any | Stored calculation incl. input snapshot |
| POST | /api/policies/bind | bind | Bind at a persisted calculation; initializes warranties |
| GET | /api/policies/{id} | any | Policy + coverages |
| PUT | /api/policies/{id}/coverages | quote | Edit limits/deductibles/enabled (blocked when bound) |
| GET | /api/policies/{id}/warranties | any | Warranty cards + no-reprice note |
| GET | /api/policies/{id}/warranty-events | any | Timestamped transitions |
| GET | /api/audit?event_type=&entity_id=&actor= | any | Filterable audit log |
| GET | /api/regulatory | — | Indian regulatory context + disclaimer |
| GET/PUT | /api/admin/config | admin | Loadings, caps, gate mode (audited) |
| PUT | /api/admin/controls/{id} | admin | Control weights / grace days (audited) |
| PUT | /api/admin/sectors | admin | Sector base frequencies (audited) |

Roles: CUSTOMER = read + intake; UNDERWRITER = + quote/bind/assess; ADMIN = + admin.
