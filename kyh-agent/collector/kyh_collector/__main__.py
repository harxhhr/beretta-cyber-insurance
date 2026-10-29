"""Collector command line:  python -m kyh_collector --data DIR <command>

  init                         create the database and print a one-time admin token
  add-company                  register an insured company (declared endpoint count from the proposal)
  issue-token                  create an enrollment token for a company's agents
  bind                         record the bound premium and start warranties at MET
  approve-build / approve-policy   trust an agent release hash / policy hash
  gen-cert                     create a private CA and a server certificate (needs the openssl tool)
  serve                        run the API + dashboard
  list                         print companies, agents and warranty states
  retire                       take a decommissioned host out of the fleet (audited)
  demo                         one-shot setup of a demo company for presentations
  link-platform / link-company / push-now   linked mode: feed the Beretta platform (Part 1)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

from . import core
from . import db as dbm
from . import evaluate as ev
from . import platform_link
from . import settings as settings_mod
from .server import make_server, utcnow


def _conn(data):
    os.makedirs(data, exist_ok=True)
    path = os.path.join(data, "collector.db")
    dbm.init(path)
    return dbm.connect(path)


def find_openssl() -> str:
    """openssl on PATH, or the copy that ships with Git for Windows."""
    import shutil
    found = shutil.which("openssl")
    if found:
        return found
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", ""),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
        for sub in (r"Git\mingw64\bin\openssl.exe", r"Git\usr\bin\openssl.exe"):
            cand = os.path.join(base, sub) if base else ""
            if cand and os.path.exists(cand):
                return cand
    raise FileNotFoundError("openssl not found. Install Git for Windows (it includes openssl) or add openssl "
                            "to PATH, then run again.")


def _gen_cert_python(p: dict, hostnames: list, days: int) -> None:
    """Fallback when openssl is missing or fails: the `cryptography` package (pip install cryptography)."""
    import datetime as dt
    import ipaddress
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    def write_key(key, path):
        with open(path, "wb") as fh:
            fh.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                       serialization.NoEncryption()))

    now = dt.datetime.now(dt.timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "KYH Collector Private CA")])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(minutes=5))
          .not_valid_after(now + dt.timedelta(days=days))
          .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
          .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
          .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
          .sign(ca_key, hashes.SHA256()))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    sans = []
    for h in hostnames:
        try:
            sans.append(x509.IPAddress(ipaddress.ip_address(h)))
        except ValueError:
            sans.append(x509.DNSName(h))
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostnames[0])]))
            .issuer_name(ca_name).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(days=days))
            .add_extension(x509.SubjectAlternativeName(sans), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, False, False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            # Python 3.13+ verifies strictly (VERIFY_X509_STRICT) and rejects a leaf without these.
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256()))
    write_key(ca_key, p["ca_key"])
    write_key(key, p["key"])
    for c, path in ((ca, p["ca"]), (cert, p["cert"])):
        with open(path, "wb") as fh:
            fh.write(c.public_bytes(serialization.Encoding.PEM))


def gen_cert(out_dir: str, hostnames: list, days: int = 825) -> dict:
    try:
        return _gen_cert_openssl(out_dir, hostnames, days)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        p = {k: os.path.join(out_dir, v) for k, v in
             {"ca_key": "ca.key", "ca": "ca.pem", "key": "server.key", "cert": "server.pem"}.items()}
        try:
            _gen_cert_python(p, hostnames, days)
        except ImportError:
            raise RuntimeError(f"Could not create the certificate ({exc}). Install Git for Windows (includes "
                               f"openssl) or run: python -m pip install cryptography") from exc
        return p


def _gen_cert_openssl(out_dir: str, hostnames: list, days: int = 825) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    p = {k: os.path.join(out_dir, v) for k, v in
         {"ca_key": "ca.key", "ca": "ca.pem", "key": "server.key", "csr": "server.csr", "cert": "server.pem"}.items()}
    san = ",".join(("IP:" if h.replace(".", "").isdigit() or ":" in h else "DNS:") + h for h in hostnames)

    openssl = find_openssl()

    def run(args):
        subprocess.run([openssl] + args[1:], check=True, capture_output=True)

    run(["openssl", "req", "-x509", "-newkey", "rsa:3072", "-nodes", "-keyout", p["ca_key"], "-out", p["ca"],
         "-days", str(days), "-subj", "/CN=KYH Collector Private CA", "-addext", "basicConstraints=critical,CA:TRUE",
         "-addext", "keyUsage=critical,keyCertSign,cRLSign", "-addext", "subjectKeyIdentifier=hash"])
    run(["openssl", "req", "-newkey", "rsa:2048", "-nodes", "-keyout", p["key"], "-out", p["csr"],
         "-subj", f"/CN={hostnames[0]}"])
    with tempfile.NamedTemporaryFile("w", suffix=".ext", delete=False) as ext:
        ext.write(f"subjectAltName={san}\nbasicConstraints=critical,CA:FALSE\n"
                  f"keyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n"
                  f"subjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid:always\n")
    try:
        run(["openssl", "x509", "-req", "-in", p["csr"], "-CA", p["ca"], "-CAkey", p["ca_key"], "-CAcreateserial",
             "-out", p["cert"], "-days", str(days), "-sha256", "-extfile", ext.name])
    finally:
        os.unlink(ext.name)
    for k in ("ca_key", "key"):
        os.chmod(p[k], 0o600)
    return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kyh-collector")
    ap.add_argument("--data", default="./collector-data", help="data directory (database, settings)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    c = sub.add_parser("add-company")
    c.add_argument("--name", required=True)
    c.add_argument("--declared-endpoints", type=int, required=True)
    c.add_argument("--sector", default="")
    c.add_argument("--demo", action="store_true", help="accept SIMULATED reports for this company")
    c.add_argument("--id", default=None)
    t = sub.add_parser("issue-token")
    t.add_argument("--company", required=True)
    t.add_argument("--max-uses", type=int, default=50)
    t.add_argument("--days", type=int, default=7)
    b = sub.add_parser("bind")
    b.add_argument("--company", required=True)
    b.add_argument("--premium", type=int, required=True, help="bound premium in INR, from Engine B")
    for name in ("approve-build", "approve-policy"):
        x = sub.add_parser(name)
        x.add_argument("--hash", required=True)
        x.add_argument("--label", default="")
    g = sub.add_parser("gen-cert")
    g.add_argument("--host", action="append", required=True, help="hostname or IP agents will use (repeatable)")
    g.add_argument("--out", default=None)
    s = sub.add_parser("serve")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8443)
    s.add_argument("--tls-cert", default=None)
    s.add_argument("--tls-key", default=None)
    sub.add_parser("list")
    lp = sub.add_parser("link-platform", help="connect this collector to the Beretta platform (Part 1)")
    lp.add_argument("--url", required=True, help="Beretta platform base URL, e.g. http://127.0.0.1:8000")
    lp.add_argument("--collector-id", required=True, help="COL-... from the platform's Admin page")
    lp.add_argument("--secret", required=True, help="secret shown once by the platform")
    lp.add_argument("--ca-file", default=None)
    lp.add_argument("--dashboard-url", default=None, help="this collector's dashboard URL, for links back")
    lc = sub.add_parser("link-company", help="map a collector company to a Beretta platform company")
    lc.add_argument("--company", required=True)
    lc.add_argument("--platform-company", required=True, help="CO-... id in the Beretta platform")
    pn = sub.add_parser("push-now", help="send the current fleet roll-up of linked companies immediately")
    pn.add_argument("--company", default=None)
    rt = sub.add_parser("retire", help="remove a host from the fleet (decommissioned machine)")
    rt.add_argument("--agent", required=True)
    rt.add_argument("--reason", default="decommissioned")
    d = sub.add_parser("demo")
    d.add_argument("--agent-dir", default=os.path.join(os.path.dirname(__file__), "..", "..", "agent"))
    a = ap.parse_args(argv)
    now = utcnow()

    if a.cmd == "gen-cert":
        paths = gen_cert(a.out or os.path.join(a.data, "tls"), a.host)
        print(json.dumps(paths, indent=2))
        print("Give ca.pem to agents (--ca-file). Keep ca.key offline.")
        return 0

    if a.cmd == "link-platform":
        path = platform_link.save_link(a.data, a.url, a.collector_id, a.secret, a.ca_file, a.dashboard_url)
        print(f"Link saved to {path} (owner-only). Restart `serve` to start pushing roll-ups.")
        return 0

    if a.cmd == "push-now":
        from .server import App
        app = App(a.data)
        if not app.link:
            print("error: not linked; run link-platform first", file=sys.stderr)
            return 1
        conn = app.conn()
        ids = [a.company] if a.company else [r["id"] for r in conn.execute(
            "SELECT id FROM companies WHERE platform_company_id IS NOT NULL")]
        conn.close()
        for cid in ids:
            r = platform_link.sync_company(app, cid, app.link, force=True)
            print(cid, "HTTP", r.get("status"), json.dumps(r.get("response"), default=str)[:400])
        return 0

    if a.cmd == "serve":
        httpd = make_server(a.data, a.host, a.port, a.tls_cert, a.tls_key)
        scheme = "https" if a.tls_cert else "http"
        print(f"Beretta collector listening on {scheme}://{a.host}:{a.port}  (dashboard at /)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0

    conn = _conn(a.data)
    s = settings_mod.load(a.data)
    conn.execute("BEGIN IMMEDIATE")
    try:
        if a.cmd == "init":
            token = core.create_admin_token(conn, now)
            print(f"Collector initialised in {os.path.abspath(a.data)}")
            print(f"Admin token (shown once, store it safely): {token}")
        elif a.cmd == "add-company":
            cid = core.add_company(conn, now, a.name, a.declared_endpoints, a.sector, a.demo, a.id)
            print(cid)
        elif a.cmd == "issue-token":
            print(core.issue_enrollment_token(conn, now, a.company, a.max_uses, a.days))
        elif a.cmd == "bind":
            core.bind_policy(conn, now, a.company, a.premium, s)
            print(f"Bound {a.company} at INR {a.premium:,}. Warranties start at MET.")
        elif a.cmd in ("approve-build", "approve-policy"):
            core.approve(conn, now, "approved_builds" if a.cmd == "approve-build" else "approved_policies",
                         a.hash, a.label)
            print("approved")
        elif a.cmd == "link-company":
            platform_link.link_company(conn, now, a.company, a.platform_company)
            print(f"{a.company} -> Beretta platform company {a.platform_company}. "
                  f"Warranties for it are now owned by the platform.")
        elif a.cmd == "retire":
            core.retire_agent(conn, now, a.agent, a.reason)
            print(f"{a.agent} retired; it no longer counts toward coverage or warranties")
        elif a.cmd == "list":
            for co in conn.execute("SELECT * FROM companies ORDER BY name").fetchall():
                snap = ev.evaluate_company(conn, co["id"], now, s)
                print(f"\n{co['name']} [{co['id']}] policy={snap['policy']['status']} "
                      f"coverage={snap['coverage']['reason']}")
                for w in snap["warranties"]:
                    print(f"   warranty {w['control']:<20} {w['state']:<11} {w.get('last_reason') or ''}")
                for h in snap["hosts"]:
                    print(f"   host {h['hostname']:<24} {h['liveness']['state']:<10} last_seen={h['last_seen']}")
        elif a.cmd == "demo":
            sys.path.insert(0, os.path.abspath(a.agent_dir))
            from kyh_agent import policy as agent_policy  # noqa: E402
            from kyh_agent.security import build_hash  # noqa: E402
            token = core.create_admin_token(conn, now)
            cid = core.add_company(conn, now, "Kalinga Components Pvt Ltd", 4, "Manufacturing", True, "co_kalinga")
            enr = core.issue_enrollment_token(conn, now, cid, 20, 30)
            core.approve(conn, now, "approved_builds", build_hash(), "kyh-agent 2.0.0 (demo)")
            core.approve(conn, now, "approved_policies", agent_policy.load().hash, "baseline 2.1.0")
            core.bind_policy(conn, now, cid, 245000, s)
            print(json.dumps({"admin_token": token, "company_id": cid, "enrollment_token": enr}, indent=2))
        conn.execute("COMMIT")
    except core.ApiError as e:
        conn.execute("ROLLBACK")
        print(f"error: {e.message}", file=sys.stderr)
        return 1
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
