"""Live presentation demo: a collector + four simulated endpoints in one process.

    python scripts/run_demo.py            # realistic grace periods (days)
    python scripts/run_demo.py --fast     # grace periods of ~3 minutes so the full lifecycle fits in a demo

Then open the printed URL, paste the admin token, and type commands here:
    break <host> <profile>   e.g.  break KAL-PLANT-WS03 edr_down   (profiles: edr_down, edr_stale,
                                   patch_overdue, backup_stale, mixed)
    fix <host>               host goes back to the healthy profile
    status                   print warranty states
    quit
All endpoint data is SIMULATED and labelled as such; the demo company runs in demo mode.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "agent"), os.path.join(ROOT, "collector")]

from kyh_agent import config as config_mod  # noqa: E402
from kyh_agent import policy as policy_mod  # noqa: E402
from kyh_agent.agent import Agent, enroll  # noqa: E402
from kyh_agent.security import build_hash  # noqa: E402
from kyh_agent.simulate import registry_for  # noqa: E402
from kyh_collector import core, evaluate as ev  # noqa: E402
from kyh_collector.__main__ import gen_cert  # noqa: E402
from kyh_collector.server import make_server  # noqa: E402

HOSTS = ["KAL-FIN-LT01", "KAL-HR-LT02", "KAL-PLANT-WS03", "KAL-SRV-ERP01"]
FAST = {"grace_days": {"PATCH": 0.003, "EDR": 0.002, "BACKUP": 0.002, "MFA": 0.002, "MONITORING_COVERAGE": 0.003},
        "remediation_confirm_hours": 0.03, "coverage_onboarding_days": 0.002}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--port", type=int, default=8443)
    ap.add_argument("--data", default=os.path.join(ROOT, "demo-data"))
    ap.add_argument("--no-input", action="store_true", help="run without the command prompt (for recordings)")
    a = ap.parse_args()

    shutil.rmtree(a.data, ignore_errors=True)
    os.makedirs(os.path.join(a.data, "collector"))
    if a.fast:
        with open(os.path.join(a.data, "collector", "settings.json"), "w") as fh:
            json.dump(FAST, fh, indent=2)
    tls = gen_cert(os.path.join(a.data, "tls"), ["localhost", "127.0.0.1"]) if shutil.which("openssl") else None
    httpd = make_server(os.path.join(a.data, "collector"), "127.0.0.1", a.port,
                        tls and tls["cert"], tls and tls["key"])
    url = f"{'https' if tls else 'http'}://localhost:{a.port}"
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    app = httpd.app
    conn = app.conn()
    now = app.clock()
    admin = core.create_admin_token(conn, now)
    cid = core.add_company(conn, now, "Kalinga Components Pvt Ltd", len(HOSTS), "Manufacturing", True, "co_kalinga")
    token = core.issue_enrollment_token(conn, now, cid, 20, 30)
    core.approve(conn, now, "approved_builds", build_hash(), "kyh-agent 2.0.0")
    core.approve(conn, now, "approved_policies", policy_mod.load().hash, "baseline 2.0.0")
    core.bind_policy(conn, now, cid, 245000, app.settings)
    conn.close()

    pol = policy_mod.load()
    agents = {}
    for h in HOSTS:
        state = os.path.join(a.data, "agents", h)
        cfg = config_mod.load(os.path.join(state, "config.json"))
        enroll(cfg, url, token, tls and tls["ca"], pol, hostname=h)
        cfg["os_override"] = "Windows Server 2022 (simulated)" if "SRV" in h else "Windows 11 Pro 24H2 (simulated)"
        agents[h] = Agent(cfg, pol, state, simulate="healthy", platform="windows")

    lock = threading.Lock()

    def push(h, profile=None):
        ag = agents[h]
        with lock:
            if profile:
                ag.simulate = profile
                ag.runner.registry = registry_for(profile, ag.platform)
            ag.scan(force_full=True)
            ag.flush()

    for h in HOSTS:
        push(h)

    def heartbeat_loop():
        while True:
            time.sleep(30)
            for h, ag in agents.items():
                with lock:
                    ag.enqueue("heartbeat", [])
                    ag.flush()

    threading.Thread(target=heartbeat_loop, daemon=True).start()
    print(f"\nDashboard: {url}   (certificate is from the demo's private CA; accept it in the browser)")
    print(f"Admin token: {admin}\n")
    if a.no_input:
        with open(os.path.join(a.data, "demo.json"), "w") as fh:
            json.dump({"url": url, "admin_token": admin, "company_id": cid}, fh)
        while True:
            time.sleep(3600)
    print("Open" + __doc__.split("Then open", 1)[1])
    while True:
        try:
            line = input("kyh-demo> ").strip().split()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line[0] == "quit":
            break
        if line[0] == "break" and len(line) == 3 and line[1] in agents:
            push(line[1], line[2])
            print(f"{line[1]} now reporting profile '{line[2]}'")
        elif line[0] == "fix" and len(line) == 2 and line[1] in agents:
            push(line[1], "healthy")
            print(f"{line[1]} healthy again")
        elif line[0] == "status":
            c = app.conn()
            c.execute("BEGIN IMMEDIATE")
            snap = ev.evaluate_company(c, cid, app.clock(), app.settings)
            c.execute("COMMIT")
            c.close()
            for w in snap["warranties"]:
                print(f"  {w['control']:<20} {w['state']:<11} {w.get('last_reason') or ''}")
        else:
            print("commands: break <host> <profile> | fix <host> | status | quit   hosts: " + ", ".join(HOSTS))
    httpd.shutdown()


if __name__ == "__main__":
    main()
