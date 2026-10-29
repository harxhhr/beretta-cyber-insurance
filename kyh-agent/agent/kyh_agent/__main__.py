"""Command-line entry point:  python -m kyh_agent <command>

  enroll       exchange a one-time company token for this machine's identity
  run          service mode: loop forever (what systemd / Task Scheduler / launchd start)
  once         run every check now, print the results, send one full report
  scan-now     ask the running service to scan now (all checks or --control X) and send at once
  status       show the last results and outbox depth (local, no network)
  show-policy  print exactly what the agent checks and what it never collects
  build-info   print the version, build hash and policy hash (for collector approval)
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from . import config as config_mod
from . import policy as policy_mod
from .agent import SCAN_REQUEST, Agent, enroll, request_scan
from .security import build_hash

COLORS = {"PASS": "\033[32m", "FAIL": "\033[31m", "ERROR": "\033[33m"}
RESET = "\033[0m"


def _color(status: str, use: bool) -> str:
    return f"{COLORS.get(status, '')}{status:<16}{RESET if status in COLORS else ''}" if use else f"{status:<16}"


def print_table(results, policy, use_color=True) -> None:
    order = {c["id"]: i for i, c in enumerate(policy.checks)}
    print(f"\n  {'TIER':<11}{'CONTROL':<18}{'STATUS':<16}{'ASSURANCE':<11}SUMMARY")
    print("  " + "-" * 110)
    for r in sorted(results, key=lambda r: order.get(r["check_id"], 99)):
        summary = r["summary"] if len(r["summary"]) <= 70 else r["summary"][:67] + "..."
        print(f"  {r['tier']:<11}{r['control']:<18}{_color(r['status'], use_color)}{(r.get('assurance') or '-'):<11}"
              f"{summary}")
    print()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kyh-agent", description="KYH live monitoring agent (read-only)")
    ap.add_argument("--config", default=None, help=f"config file (default {config_mod.DEFAULT_CONFIG})")
    ap.add_argument("--state-dir", default=None, help=f"state directory (default {config_mod.DEFAULT_STATE})")
    ap.add_argument("--policy", default=None, help="policy file (default: the one shipped with the agent)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("enroll")
    e.add_argument("--server", required=True, help="collector URL, e.g. https://collector.example:8443")
    e.add_argument("--token", required=True, help="one-time enrollment token from the insurer")
    e.add_argument("--ca-file", default=None, help="collector CA certificate to pin (PEM)")
    e.add_argument("--allow-insecure-http", action="store_true", help="lab use only")
    e.add_argument("--hostname", default=None, help="report this name instead of the OS hostname (demos)")

    r = sub.add_parser("run")
    r.add_argument("--simulate", default=None, help="demo profile (results are labelled SIMULATED)")
    r.add_argument("--tick", type=int, default=30)

    o = sub.add_parser("once")
    o.add_argument("--simulate", default=None)
    o.add_argument("--no-send", action="store_true", help="run checks and print only")
    o.add_argument("--json", action="store_true", help="print the full JSON envelope")

    sn = sub.add_parser("scan-now")
    sn.add_argument("--control", action="append", default=[], help="e.g. FIREWALL, EDR (repeatable); default all")
    sn.add_argument("--wait", type=int, default=0, metavar="SECONDS",
                    help="wait up to this long for the service to finish and print the new results")

    sub.add_parser("status")
    sub.add_parser("show-policy")
    sub.add_parser("build-info")

    a = ap.parse_args(argv)
    cfg = config_mod.load(a.config)
    state_dir = a.state_dir or config_mod.DEFAULT_STATE
    pol = policy_mod.load(a.policy)
    color = sys.stdout.isatty() and os.name != "nt"

    if a.cmd == "build-info":
        print(json.dumps({"version": __version__, "build_hash": build_hash(), "policy_id": pol.id,
                          "policy_version": pol.version, "policy_hash": pol.hash}, indent=2))
        return 0

    if a.cmd == "show-policy":
        print(f"{pol.meta['name']}  (v{pol.version}, hash {pol.hash[:12]})\n")
        for c in pol.checks:
            print(f"  [{c['tier']:<10}] {c['control']:<17} every {c.get('interval_minutes')} min  {c['title']}")
        print("\n  COLLECTED: control states, OS version, hostname, counts, configuration values,")
        print("             salted hashes of admin account names.")
        print("  NEVER COLLECTED: file contents, documents, browsing history, keystrokes, screenshots,")
        print("             e-mail, passwords, usernames in clear text, personal data of employees.")
        print(f"  A local copy of every report sent is written to {os.path.join(state_dir, 'sent.jsonl')}")
        return 0

    if a.cmd == "enroll":
        info = enroll(cfg, a.server, a.token, a.ca_file, pol, allow_insecure_http=a.allow_insecure_http,
                      hostname=a.hostname)
        print(f"Enrolled as {info['agent_id']} for {info['company']}. Config written to {cfg.path}")
        if info["clock_skew_seconds"] and info["clock_skew_seconds"] > 300:
            print(f"WARNING: local clock differs from the collector by {info['clock_skew_seconds']} s")
        return 0

    if a.cmd == "scan-now":
        import time
        known = {c["control"] for c in pol.checks}
        bad = [c for c in a.control if c.upper() not in known]
        if bad:
            print(f"Unknown control(s): {', '.join(bad)}. Known: {', '.join(sorted(known))}", file=sys.stderr)
            return 1
        from datetime import datetime
        state_path = os.path.join(state_dir, "state.json")
        asked = datetime.now().astimezone().replace(microsecond=0)
        request_scan(state_dir, a.control)
        what = ", ".join(c.upper() for c in a.control) or "all checks"
        print(f"Scan requested ({what}). The running agent picks it up within its tick (about 30 s).")
        if not a.wait:
            return 0
        deadline = time.time() + a.wait
        flag = os.path.join(state_dir, SCAN_REQUEST)
        while time.time() < deadline:
            st = {}
            if not os.path.exists(flag) and os.path.exists(state_path):
                try:
                    with open(state_path, encoding="utf-8") as fh:
                        st = json.load(fh)
                except (OSError, ValueError):
                    st = {}
            last = st.get("last_scan_at")
            if last and datetime.fromisoformat(last.replace("Z", "+00:00")) >= asked:
                time.sleep(3)  # the service sends right after saving its state
                res = list(st.get("last_results", {}).values())
                if a.control:
                    res = [r for r in res if r["control"] in {c.upper() for c in a.control}]
                print_table(res, pol, color)
                return 0
            time.sleep(1)
        print("No scan seen yet. Is the agent service running? (Get-ScheduledTask 'KYH Live Monitoring Agent')",
              file=sys.stderr)
        return 3

    if a.cmd == "status":
        path = os.path.join(state_dir, "state.json")
        if not os.path.exists(path):
            print("No results yet. Run `kyh-agent once`.")
            return 1
        with open(path, encoding="utf-8") as fh:
            st = json.load(fh)
        agent_id = cfg.get("agent_id", "not enrolled")
        print(f"Agent {agent_id}  company={cfg.get('company_name', '-')}  last scan={st.get('last_scan_at')}")
        from .spool import Spool
        print(f"Outbox depth: {Spool(os.path.join(state_dir, 'outbox.db')).depth()} report(s) waiting")
        print_table(list(st.get("last_results", {}).values()), pol, color)
        return 0

    agent = Agent(cfg, pol, state_dir, simulate=getattr(a, "simulate", None))

    if a.cmd == "once":
        if a.no_send:
            results = [x.to_dict() for x in agent.runner.run()]
            if a.json:
                print(json.dumps(agent.envelope("full", results, 0), indent=2))
            else:
                print_table(results, pol, color)
            return 0
        out = agent.scan(force_full=True)
        agent.heartbeat_if_due()
        stats = agent.flush()
        print_table(list(agent.state["last_results"].values()), pol, color)
        print(f"Report queued ({out['ran']} checks). Sent: {stats['sent']}, rejected: {stats['rejected']}, "
              f"waiting: {stats['remaining']}" + (f"  [{stats['error']}]" if stats["error"] else ""))
        return 0 if not stats["rejected"] else 2

    if a.cmd == "run":
        if not cfg.enrolled and not a.simulate:
            print("Not enrolled. Run `kyh-agent enroll --server ... --token ...` first.", file=sys.stderr)
            return 1
        agent.run_forever(tick_seconds=a.tick)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
