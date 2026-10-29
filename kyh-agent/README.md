# Beretta Live Monitoring Agent (v2.0.0)

Part 2 of the Beretta capstone. The **agent** runs on an insured company's machines, checks twelve
security controls read-only, and sends signed reports. The **collector** checks each report, rolls the results up
across the fleet, and runs the post-bind warranty state machine (MET → IN_GRACE → BREACHED → REMEDIATED).
Neither one touches the premium.

Python 3.9+ standard library only. No pip installs.

```
agent/        kyh_agent package + installers (Windows, Linux, macOS)
collector/    kyh_collector package + web dashboard
tests/        144 unit, integration and HTTPS end-to-end tests
scripts/      run_demo.py (live presentation demo)
docs/         explanation document, figures, figure generator
```

## Quick start (one laptop)

```bash
python run_tests.py                     # 144 tests
python scripts/run_demo.py --fast       # collector + 4 simulated endpoints, ~3-minute grace periods
```

Open the printed URL, paste the admin token, then type `break KAL-PLANT-WS03 edr_down` at the `kyh-demo>` prompt.

## Real deployment (summary)

On the insurer's server:

```bash
export PYTHONPATH=collector:agent
python -m kyh_collector --data /srv/kyh init                      # prints the admin token once
python -m kyh_collector --data /srv/kyh gen-cert --host collector.example.in
python -m kyh_collector --data /srv/kyh add-company --name "Kalinga Components" --declared-endpoints 40
python -m kyh_collector --data /srv/kyh bind --company co_xxx --premium 245000
python -m kyh_agent build-info                                    # prints build_hash and policy_hash
python -m kyh_collector --data /srv/kyh approve-build  --hash <build_hash>  --label "2.0.0"
python -m kyh_collector --data /srv/kyh approve-policy --hash <policy_hash> --label "baseline 2.0.0"
python -m kyh_collector --data /srv/kyh issue-token --company co_xxx --max-uses 45 --days 14
python -m kyh_collector --data /srv/kyh serve --host 0.0.0.0 --port 8443 \
       --tls-cert /srv/kyh/tls/server.pem --tls-key /srv/kyh/tls/server.key
```

On each insured endpoint (admin rights), with `ca.pem` and the enrollment token:

```powershell
# Windows
.\agent\install\windows\install.ps1 -Server https://collector.example.in:8443 -Token kyh_enr_... -CaFile .\ca.pem
```
```bash
# Linux
sudo ./agent/install/linux/install.sh --server https://collector.example.in:8443 --token kyh_enr_... --ca-file ca.pem
```

## Agent commands

| Command | What it does |
|---|---|
| `python -m kyh_agent once --no-send` | run every check and print a table (nothing leaves the machine) |
| `python -m kyh_agent status` | last results and outbox depth |
| `python -m kyh_agent show-policy` | what is checked, how often, and what is never collected |
| `python -m kyh_agent build-info` | version, build hash, policy hash |

The full explanation, including the design decisions, security model and limitations, is in
`docs/Beretta_Live_Monitoring_Agent.docx`.

## Linked mode (feeding the Beretta platform, Part 1)

When a company is linked, the Beretta platform owns its warranties and the collector stops running
its own state machine for it. The collector still does everything endpoint-related and pushes
one signed fleet roll-up per company to the platform: on every change, and as a heartbeat every
15 minutes. Several collector controls can feed one platform control (it fails if any of them
fails); controls no host can observe, such as MFA, are not sent; a passing BACKUP is sent as
`partial` because restore tests are not observable from endpoints.

```bash
# after registering the collector on the platform (Admin → Monitoring collectors)
python -m kyh_collector --data /srv/kyh link-platform --url https://kyh.example.in \
       --collector-id COL-xxxx --secret <shown once> --dashboard-url https://collector.example.in:8443
python -m kyh_collector --data /srv/kyh link-company --company co_xxxx --platform-company CO-xxxx
python -m kyh_collector --data /srv/kyh serve ...       # starts the link worker
python -m kyh_collector --data /srv/kyh push-now        # optional: push immediately
```

The mapping is in `collector/kyh_collector/settings.py` (`platform_control_map`).
