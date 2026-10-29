#!/usr/bin/env python3
"""KYH Cyber Insurance endpoint agent — standard library only.

Designed for AUTHORIZED deployment on insured company systems. Performs
read-only defensive checks (see checks.py) and reports structured JSON to the
platform. Checks that cannot be observed on this platform report
NOT_SUPPORTED — never a fabricated result.

Usage:
    python agent.py --once                       # run checks, report, exit
    python agent.py --print                      # run checks, print JSON only
    python agent.py --interval 300               # periodic reporting
    python agent.py --simulate mixed --once      # demo profile (labelled SIMULATED)

Configuration: agent/config.json
    { "server_url": "http://127.0.0.1:8000",
      "agent_token": "<token issued by the platform>",
      "agent_id": "<agent id>" }
Environment overrides: KYH_SERVER, KYH_AGENT_TOKEN, KYH_AGENT_ID (legacy CYBERUW_* also accepted).
"""
import argparse
import json
import logging
import os
import platform
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checks  # noqa: E402

log = logging.getLogger("kyh-agent")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config(path):
    cfg = {}
    if os.path.exists(path):
        with open(path) as fh:
            cfg = json.load(fh)
    env = lambda new, old: os.environ.get(new) or os.environ.get(old)
    cfg["server_url"] = env("KYH_SERVER", "CYBERUW_SERVER") or cfg.get(
        "server_url", "http://127.0.0.1:8000")
    cfg["agent_token"] = env("KYH_AGENT_TOKEN", "CYBERUW_AGENT_TOKEN") or cfg.get("agent_token")
    cfg["agent_id"] = env("KYH_AGENT_ID", "CYBERUW_AGENT_ID") or cfg.get("agent_id")
    return cfg


def build_report(cfg, simulate=None):
    results = checks.run_simulated(simulate) if simulate else checks.run_all()
    return {
        "agent_id": cfg.get("agent_id"),
        "hostname": socket.gethostname(),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "simulated_profile": simulate,
        "checks": results,
    }


def send_report(cfg, report):
    url = cfg["server_url"].rstrip("/") + "/api/agent/report"
    req = urllib.request.Request(
        url, data=json.dumps(report).encode(), method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {cfg['agent_token']}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        log.error("Server rejected report (%s): %s", e.code, body[:300])
        return None
    except (urllib.error.URLError, TimeoutError) as e:
        log.error("Could not reach server: %s", e)
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=CONFIG_PATH)
    ap.add_argument("--once", action="store_true", help="report once and exit")
    ap.add_argument("--print", dest="print_only", action="store_true",
                    help="print report JSON without sending")
    ap.add_argument("--interval", type=int, default=0,
                    help="seconds between periodic reports")
    ap.add_argument("--simulate", choices=sorted(checks.SIM_PROFILES),
                    help="use a labelled SIMULATED demo profile instead of real checks")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    cfg = load_config(args.config)
    if not args.print_only and not cfg.get("agent_token"):
        log.error("No agent token configured (config.json or KYH_AGENT_TOKEN).")
        sys.exit(2)

    def cycle():
        report = build_report(cfg, simulate=args.simulate)
        supported = sum(1 for c in report["checks"] if c["status"] != "NOT_SUPPORTED")
        log.info("Ran %d checks (%d observable, %d NOT_SUPPORTED)%s",
                 len(report["checks"]), supported,
                 len(report["checks"]) - supported,
                 f" [SIMULATED profile '{args.simulate}']" if args.simulate else "")
        if args.print_only:
            print(json.dumps(report, indent=2))
            return
        resp = send_report(cfg, report)
        if resp:
            log.info("Server accepted report %s: %d observations recorded; "
                     "repricing_performed=%s; warranty_evaluation=%s",
                     resp.get("report_id"), resp.get("observations_recorded", 0),
                     resp.get("repricing_performed"),
                     json.dumps(resp.get("warranty_evaluation")))

    if args.interval > 0 and not args.once:
        log.info("Periodic reporting every %ds. Ctrl+C to stop.", args.interval)
        while True:
            cycle()
            time.sleep(max(30, args.interval))
    else:
        cycle()


if __name__ == "__main__":
    main()
