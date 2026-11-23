#!/bin/sh
# Apply mynebula host policy (docs/host-policy.md) on a node. Idempotent; run as root.
# CPU_CAP_W: default 30 on laptop-class hosts (battery present), unset (no cap) otherwise.
set -eu
log(){ echo "apply-host-policy: $*"; }
is_laptop(){ ls /sys/class/power_supply/BAT* >/dev/null 2>&1; }

# 1. Power cap (laptops only unless CPU_CAP_W is set)
if [ -z "${CPU_CAP_W:-}" ] && is_laptop; then CPU_CAP_W=30; fi
if [ -n "${CPU_CAP_W:-}" ]; then
  cat > /usr/local/sbin/mynebula-cpu-cap <<'S'
#!/bin/sh
# Re-applied by timer: thermald/firmware rewrite RAPL limits after boot. Logs only on drift.
W=${CPU_CAP_W:-30}; U=$((W*1000000))
for z in /sys/class/powercap/intel-rapl:0; do
  [ -w $z/constraint_0_power_limit_uw ] || continue
  for c in 0 1; do
    cur=$(cat $z/constraint_${c}_power_limit_uw)
    if [ "$cur" != "$U" ]; then
      echo $U > $z/constraint_${c}_power_limit_uw
      logger -t mynebula-cpu-cap "$z c$c was $((cur/1000000))W -> ${W}W"
    fi
  done
done
S
  chmod 0755 /usr/local/sbin/mynebula-cpu-cap
  printf '[Unit]\nDescription=MyNebula CPU package power cap (RAPL)\nAfter=thermald.service\n[Service]\nType=oneshot\nEnvironment=CPU_CAP_W=%s\nExecStart=/usr/local/sbin/mynebula-cpu-cap\n' "$CPU_CAP_W" > /etc/systemd/system/mynebula-cpu-cap.service
  printf '[Unit]\nDescription=Re-apply MyNebula CPU power cap every minute\n[Timer]\nOnBootSec=20s\nOnCalendar=*:*:00\nAccuracySec=5s\n[Install]\nWantedBy=timers.target\n' > /etc/systemd/system/mynebula-cpu-cap.timer
  systemctl daemon-reload
  systemctl stop mynebula-cpu-cap.service 2>/dev/null || true
  systemctl enable --now mynebula-cpu-cap.timer
  TIMERS=$(systemctl list-timers mynebula-cpu-cap.timer --no-pager 2>&1 || true)
  printf '%s\n' "$TIMERS"
  if ! printf '%s\n' "$TIMERS" | awk '$0 ~ /mynebula-cpu-cap\.timer/ && $1 !~ /^[-]+$/ && $1 != "n/a" {ok=1} END{exit !ok}'; then
    echo "apply-host-policy: mynebula-cpu-cap.timer has no NEXT" >&2
    exit 1
  fi
  log "CPU cap ${CPU_CAP_W} W (timer)"
else
  log "no battery and CPU_CAP_W unset: no CPU cap"
fi

# 1b. No turbo on laptops (owner policy: quiet over fast; runtime value + tmpfiles persistence)
if is_laptop && [ -w /sys/devices/system/cpu/intel_pstate/no_turbo ]; then
  printf 'w /sys/devices/system/cpu/intel_pstate/no_turbo - - - - 1\n' > /etc/tmpfiles.d/mynebula-no-turbo.conf
  systemd-tmpfiles --create /etc/tmpfiles.d/mynebula-no-turbo.conf || log "no_turbo tmpfiles unsupported"
  log "no_turbo=$(cat /sys/devices/system/cpu/intel_pstate/no_turbo)"
fi

# 2. RAPL energy readable for the Prometheus node exporter
echo 'SUBSYSTEM=="powercap", ACTION=="add", RUN+="/bin/chmod 0444 /sys%p/energy_uj"' > /etc/udev/rules.d/60-rapl-readable.rules
chmod 0444 /sys/class/powercap/intel-rapl*/energy_uj /sys/class/powercap/intel-rapl*/intel-rapl*/energy_uj 2>/dev/null || true

# 3. KSM with the kernel scan-time advisor
cat > /etc/tmpfiles.d/mynebula-ksm.conf <<'K'
w /sys/kernel/mm/ksm/run - - - - 1
w /sys/kernel/mm/ksm/advisor_mode - - - - scan-time
w /sys/kernel/mm/ksm/advisor_max_cpu - - - - 10
w /sys/kernel/mm/ksm/advisor_target_scan_time - - - - 200
w /sys/kernel/mm/ksm/use_zero_pages - - - - 1
w /sys/kernel/mm/ksm/smart_scan - - - - 1
K
systemd-tmpfiles --create /etc/tmpfiles.d/mynebula-ksm.conf || log "KSM advisor unsupported by this kernel (needs 6.9+)"
log "KSM: run=$(cat /sys/kernel/mm/ksm/run) advisor=$(cat /sys/kernel/mm/ksm/advisor_mode 2>/dev/null || echo n/a)"

# 4. Frontend name over the tailnet (FRONTEND_NAME / FRONTEND_TS_IP)
if [ -n "${FRONTEND_TS_IP:-}" ]; then
  N=${FRONTEND_NAME:-webclip}
  grep -q " $N\b" /etc/hosts || echo "$FRONTEND_TS_IP $N # mynebula frontend (tailnet)" >> /etc/hosts
  log "hosts: $N -> $FRONTEND_TS_IP"
fi

# 5. Base-image dir on root (datastore symlink is created per datastore id by the frontend step)
install -d -o oneadmin -g oneadmin -m 0750 /srv/one-images 2>/dev/null || true
# 6. Whole-platform power (RAPL psys) for Prometheus via the node_exporter textfile collector
install -d -m 0755 /var/lib/node_exporter/textfile
cat > /usr/local/sbin/mynebula-psys-prom <<'Q'
#!/bin/sh
D=/var/lib/node_exporter/textfile; Z=$(grep -l "^psys$" /sys/class/powercap/intel-rapl:*/name 2>/dev/null | head -1)
[ -n "$Z" ] || exit 0
E=$(cat $(dirname $Z)/energy_uj)
printf "# HELP mynebula_rapl_psys_joules_total RAPL psys (whole platform) energy.\n# TYPE mynebula_rapl_psys_joules_total counter\nmynebula_rapl_psys_joules_total %s\n" $(awk -v e=$E 'BEGIN{printf "%.6f", e/1000000}') > $D/psys.prom.$$ && mv $D/psys.prom.$$ $D/psys.prom
Q
chmod 0755 /usr/local/sbin/mynebula-psys-prom
printf '[Unit]\nDescription=MyNebula psys energy for node_exporter\n[Service]\nType=oneshot\nExecStart=/usr/local/sbin/mynebula-psys-prom\n' > /etc/systemd/system/mynebula-psys-prom.service
printf '[Unit]\nDescription=MyNebula psys energy every 15s\n[Timer]\nOnBootSec=10s\nOnUnitActiveSec=15s\nAccuracySec=1s\n[Install]\nWantedBy=timers.target\n' > /etc/systemd/system/mynebula-psys-prom.timer
if systemctl list-unit-files opennebula-node-exporter.service >/dev/null 2>&1; then
  mkdir -p /etc/systemd/system/opennebula-node-exporter.service.d
  printf '[Service]\nExecStart=\nExecStart=/usr/bin/node_exporter --collector.textfile.directory=/var/lib/node_exporter/textfile\n' > /etc/systemd/system/opennebula-node-exporter.service.d/textfile.conf
fi
systemctl daemon-reload; systemctl enable --now mynebula-psys-prom.timer
systemctl try-restart opennebula-node-exporter.service || true
log "psys exporter: mynebula_rapl_psys_joules_total"
log "done"
