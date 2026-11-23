#!/bin/sh
# Install mynebula-fan-counter on a node. Run as root. Idempotent.
# Same artifacts as scripts/apply-host-policy.sh section 7 in the mynebula repo.
set -eu
cd "$(dirname "$0")"

if ! grep -l '^dell_smm$' /sys/class/hwmon/hwmon*/name >/dev/null 2>&1; then
  echo "install-fan-counter: no dell_smm hwmon, nothing to do" >&2
  exit 0
fi

install -d -m 0755 /var/lib/mynebula-fan-counter
install -m 0755 mynebula-fan-counter /usr/local/sbin/mynebula-fan-counter
install -m 0644 mynebula-fan-counter.service /etc/systemd/system/mynebula-fan-counter.service
systemctl daemon-reload
systemctl enable --now mynebula-fan-counter.service
systemctl restart mynebula-fan-counter.service
sleep 3
systemctl is-active mynebula-fan-counter.service
cat /var/lib/node_exporter/textfile/fan.prom
