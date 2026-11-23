#!/usr/bin/env bash
# READ-ONLY acceptance checks after the Ubuntu 26.10 host first boots.
set -u
failed=0
check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    printf 'PASS %s\n' "$label"
  else
    printf 'FAIL %s\n' "$label"
    failed=$((failed+1))
  fi
}
. /etc/os-release
if [[ "$ID" == ubuntu && "$VERSION_ID" == 26.10 ]]; then
  echo 'PASS Ubuntu 26.10'
else
  echo 'FAIL Ubuntu 26.10'
  failed=$((failed+1))
fi
check 'Linux 7.3-series kernel' bash -c '[[ "$(uname -r)" == 7.3.* ]]'
check 'KVM device exists' test -e /dev/kvm
check 'SSH active' systemctl is-active --quiet ssh
check 'libvirt available' command -v virsh
check 'QEMU libvirt connection' virsh -c qemu:///system list --all
check 'Tailscale daemon active' systemctl is-active --quiet tailscaled
check 'Tailscale enrolled' tailscale status
if [[ -d /sys/kernel/iommu_groups ]] && find /sys/kernel/iommu_groups -type l | grep -q .; then
  echo 'PASS IOMMU groups present'
else
  echo 'WARN IOMMU groups missing; check BIOS and kernel command line before VFIO'
fi
echo "Kernel: $(uname -r)"
echo "Failed checks: $failed"
exit "$((failed > 0))"
