#!/usr/bin/env bash
# READ-ONLY discovery. Output may contain MACs, disk serials and private host data.
set -u
section() { printf '\n===== %s =====\n' "$1"; }
run() { command -v "$1" >/dev/null 2>&1 && "$@" || true; }
section 'OS / kernel / clock'
run cat /etc/os-release
run uname -a
run timedatectl
section 'CPU / NUMA'
run lscpu
run numactl --hardware
section 'Memory'
run free -h
section 'Disks: verify exact ID_SERIAL with udevadm'
run lsblk -d -o NAME,SIZE,MODEL,SERIAL,TRAN,ROTA
section 'PCI devices'
run lspci -nnk
section 'Kernel commandline and IOMMU groups'
run cat /proc/cmdline
if [[ -d /sys/kernel/iommu_groups ]]; then
  find /sys/kernel/iommu_groups -type l | sort || true
fi
section 'Virtualization'
if [[ -e /dev/kvm ]]; then ls -l /dev/kvm; else echo '/dev/kvm missing'; fi
section 'Network and RDMA'
run ip -br link
run rdma link
run ibv_devices
section 'Libvirt'
run virsh -c qemu:///system list --all
section 'PCIe ASPM'
if [[ -e /sys/module/pcie_aspm/parameters/policy ]]; then
  cat /sys/module/pcie_aspm/parameters/policy
fi
