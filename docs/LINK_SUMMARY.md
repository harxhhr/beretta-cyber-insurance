# Beretta: platform + live monitoring

| Folder | What it is |
|---|---|
| `kyh-cyber-insurance/` | **Part 1, the Beretta platform.** Evidence → pricing at inception → bind → the warranty state machine. Owns the premium and the warranties. |
| `kyh-agent/` | **Part 2, live monitoring.** The endpoint agent and the collector. Owns everything about endpoints and sends one signed fleet roll-up per company to Part 1. |
| `integration/` | One test that runs both systems for real and checks the whole chain. |
| `run_linked_demo.py` | Both systems plus four simulated endpoints, for a presentation. |
| `docs/` | Explanation of how the two parts are linked, with screenshots. |

Python 3.9+ standard library only.

```bash
python run_linked_demo.py                                  # then open http://127.0.0.1:8000
python -m unittest discover -s kyh-cyber-insurance/tests -t kyh-cyber-insurance   # 32 tests
python kyh-agent/run_tests.py                              # 144 tests
python integration/test_linked_system.py                   # 1 end-to-end test across both
```

The one rule both parts keep: **monitoring never re-prices a bound policy.** Agent and fleet
data change warranty states only.

## How Part 1 and Part 2 are linked (Option B, 26 Oct 2026)

- The collector (Part 2) owns endpoints: agent enrollment, signed per-host reports, replay checks, silence rule (UNVERIFIED > 6 h, SILENT > 72 h), 95% fleet roll-up.
- The Beretta platform (Part 1) owns the policy: evidence resolution, pricing, bind, and the **only** warranty state machine.
- The collector pushes one HMAC-signed, sequenced roll-up per linked company to `POST /api/collector/rollup` on change and every 15 min; the platform records each result as `AGENT_FLEET` / TECHNICALLY_OBSERVED evidence (repeats within 6 h skipped) and runs `coverage.evaluate_policy`. Response carries warranty states and `repricing_performed: false`.
- Mapping (`platform_control_map`): PATCH→CTRL-PATCH-CRIT, EDR→CTRL-EDR, BACKUP→CTRL-BACKUP-TESTED (pass sent as *partial*), MFA→CTRL-MFA (never sent, not observable), DISK_ENCRYPTION→CTRL-ENCRYPTION, FIREWALL/REMOTE_ACCESS/EXPOSED_SERVICES/ADMIN_ACCOUNTS/OS_SUPPORT→CTRL-SECCONFIG, LOG_RETENTION/TIME_SYNC→CTRL-LOGGING, MONITORING_COVERAGE→CTRL-AGENT-COVERAGE. Any failing source fails the platform control; unobservable controls are not sent.
- New platform control CTRL-AGENT-COVERAGE is **monitoring only**: excluded from the posture modifier, eligibility and questionnaire, so the 15 priced controls and all premiums are unchanged. 14-day grace.
- Linked companies: collector runs no warranty state machine, refuses bind, displays platform states. Platform REMEDIATED→MET is immediate (collector's 24 h hold not used).
- Tests: Part 1 32 (17 original + 15), Part 2 144 (135 + 9), 1 cross-system integration test. Demo: `python run_linked_demo.py` (bind / break / fast-forward / fix).
- Open items: disable the legacy `/api/agent/report` endpoint once the collector is used; broader Part 1 UI redesign still to do.
