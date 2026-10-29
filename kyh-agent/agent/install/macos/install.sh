#!/usr/bin/env bash
# Install the KYH agent as a launchd daemon (macOS, best-effort platform).
#   sudo ./install.sh --server https://collector.example.in:8443 --token kyh_enr_XXXX --ca-file ca.pem
set -euo pipefail
SERVER="" TOKEN="" CA=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --server) SERVER="$2"; shift 2 ;; --token) TOKEN="$2"; shift 2 ;; --ca-file) CA="$2"; shift 2 ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
done
[[ $EUID -eq 0 ]] || { echo "run with sudo"; exit 1; }
HERE="$(cd "$(dirname "$0")/../.." && pwd)"
DATA="/Library/Application Support/KYH/Agent"

mkdir -p /Library/KYH/Agent "$DATA"
rm -rf /Library/KYH/Agent/kyh_agent && cp -R "$HERE/kyh_agent" /Library/KYH/Agent/
chown -R root:wheel /Library/KYH/Agent && chmod 700 "$DATA"
cp "$CA" "$DATA/ca.pem"

cd /Library/KYH/Agent
PYTHONPATH=/Library/KYH/Agent /usr/bin/python3 -m kyh_agent enroll --server "$SERVER" --token "$TOKEN" --ca-file "$DATA/ca.pem"

cp "$HERE/install/macos/com.kyh.agent.plist" /Library/LaunchDaemons/
chown root:wheel /Library/LaunchDaemons/com.kyh.agent.plist
launchctl bootstrap system /Library/LaunchDaemons/com.kyh.agent.plist
echo "Installed. Check with: sudo launchctl print system/com.kyh.agent"
