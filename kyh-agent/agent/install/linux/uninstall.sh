#!/usr/bin/env bash
# Remove the KYH agent. Note: the collector will see this host go SILENT after 72 h,
# which counts as failing every warranty control. Retire the host on the collector first.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "run as root (sudo)"; exit 1; }
systemctl disable --now kyh-agent.service 2>/dev/null || true
rm -f /etc/systemd/system/kyh-agent.service
systemctl daemon-reload
rm -rf /opt/kyh-agent /etc/kyh-agent /var/lib/kyh-agent
echo "KYH agent removed."
