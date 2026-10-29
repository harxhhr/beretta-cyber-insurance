#!/usr/bin/env bash
# Install the KYH agent as a systemd service.
#   sudo ./install.sh --server https://collector.example.in:8443 --token kyh_enr_XXXX --ca-file ca.pem
set -euo pipefail

SERVER="" TOKEN="" CA=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --server) SERVER="$2"; shift 2 ;;
    --token) TOKEN="$2"; shift 2 ;;
    --ca-file) CA="$2"; shift 2 ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
done
[[ $EUID -eq 0 ]] || { echo "run as root (sudo)"; exit 1; }
[[ -n "$SERVER" && -n "$TOKEN" && -n "$CA" ]] || { echo "need --server, --token and --ca-file"; exit 2; }
command -v python3 >/dev/null || { echo "python3 (3.9+) is required"; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || { echo "python3 >= 3.9 required"; exit 1; }

HERE="$(cd "$(dirname "$0")/../.." && pwd)"   # the agent/ folder

install -d -m 0755 /opt/kyh-agent
rm -rf /opt/kyh-agent/kyh_agent
cp -r "$HERE/kyh_agent" /opt/kyh-agent/
find /opt/kyh-agent -name '__pycache__' -prune -exec rm -rf {} +
chown -R root:root /opt/kyh-agent
chmod -R u=rwX,go=rX /opt/kyh-agent

install -d -m 0700 /etc/kyh-agent /var/lib/kyh-agent
install -m 0644 "$CA" /etc/kyh-agent/ca.pem

cd /opt/kyh-agent
PYTHONPATH=/opt/kyh-agent python3 -m kyh_agent enroll --server "$SERVER" --token "$TOKEN" --ca-file /etc/kyh-agent/ca.pem

install -m 0644 "$HERE/install/linux/kyh-agent.service" /etc/systemd/system/kyh-agent.service
systemctl daemon-reload
systemctl enable --now kyh-agent.service

echo
echo "Installed. Useful commands:"
echo "  systemctl status kyh-agent"
echo "  journalctl -u kyh-agent -f"
echo "  sudo PYTHONPATH=/opt/kyh-agent python3 -m kyh_agent status"
echo "  sudo PYTHONPATH=/opt/kyh-agent python3 -m kyh_agent show-policy"
