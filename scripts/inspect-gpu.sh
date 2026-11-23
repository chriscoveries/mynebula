#!/usr/bin/env bash
# Read-only NVIDIA GPU inventory for RTX 3000 Mobile qualification.
# No root, reset, clock/power writes or GPU driver binding changes.
# Review/redact output before posting externally.
set -u

section() { printf '\n===== %s =====\n' "$1"; }

section "Host OS and kernel"
if command -v uname >/dev/null 2>&1; then uname -sr; fi
if [[ -r /etc/os-release ]]; then
  grep -E '^(PRETTY_NAME|VERSION_ID)=' /etc/os-release || true
fi

section "NVIDIA PCI functions (verify 10de:1f36 or 10de:1f76)"
if command -v lspci >/dev/null 2>&1; then
  lspci -D -nnk -d 10de: || true
else
  echo "lspci unavailable; install pciutils only when approved"
fi

section "NVIDIA driver and live readings"
if command -v nvidia-smi >/dev/null 2>&1; then
  if ! nvidia-smi --query-gpu=name,pci.bus_id,driver_version,vbios_version,power.limit,clocks.gr,clocks.mem,temperature.gpu --format=csv; then
    echo "Full query unsupported; retrying minimal fields"
    nvidia-smi --query-gpu=name,driver_version,temperature.gpu --format=csv || true
  fi
  section "Power / clock / throttle reasons (read-only)"
  nvidia-smi -q -d PERFORMANCE,POWER,CLOCK || true
else
  echo "nvidia-smi unavailable; NVIDIA driver may be absent or GPU bound to vfio-pci"
fi

section "Optional tuning-tool discovery (no changes)"
if command -v nvuv >/dev/null 2>&1; then
  nvuv get || true
else
  echo "nvuv not installed"
fi
if command -v greencurve >/dev/null 2>&1; then
  echo "Green Curve found. Run 'greencurve --self-test' manually to inspect read-only capabilities."
else
  echo "Green Curve not installed"
fi

echo
echo "End of read-only inventory. No unlock or tuning applied."
