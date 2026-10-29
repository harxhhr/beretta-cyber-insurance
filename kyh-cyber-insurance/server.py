#!/usr/bin/env python3
"""Beretta — Explainable Cyber Insurance Underwriting &
Continuous Warranty Monitoring Platform — prototype server.

Run:  python server.py  [--port 8000]
Then open http://127.0.0.1:8000
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.api import make_server                       # noqa: E402
from app.database import DATA_DIR, SECRETS_PATH       # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    server = make_server(args.host, args.port)
    print("=" * 72)
    print("Beretta — Underwriting Platform (prototype)")
    print(f"Home (Questionnaires):  http://{args.host}:{args.port}")
    if os.path.exists(SECRETS_PATH):
        with open(SECRETS_PATH) as fh:
            tokens = json.load(fh)["role_tokens"]
        print("Role tokens (also in data/secrets.json — never commit this file):")
        for role, tok in tokens.items():
            print(f"  {role:<12} {tok}")
    demo = os.path.join(DATA_DIR, "demo_profiles.json")
    if os.path.exists(demo):
        print(f"Demo companies + agent tokens: {demo}")
    print("Assumptions are demonstration values — not production actuarial rates.")
    print("=" * 72)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
