# Architecture and scope

## Target topology

```text
  webclip (existing remote Linux host; frontend later)
     OpenNebula 7.4 / FireEdge / API
                     |
           Tailscale management plane
                     |
       +-------------+-------------+
       |             |             |
  hypervisor-1  hypervisor-2  hypervisor-3
  Ubuntu 26.10  Ubuntu 26.10  Ubuntu 26.10
  KVM/libvirt   KVM/libvirt   KVM/libvirt
       +---- dedicated local data/RDMA links ----+
             LAN, SFP28 / QSFP+ / DAC
```

Phase 1 is host OS and KVM, independent from the control plane. Phase 2 is OpenNebula host package compatibility and frontend enrolment. Phase 3 adds VM networks and shared/local datastores.

## Current requirements

- Linux kernel 7.3 features on Ubuntu 26.10 (interim release, security support ends July 2027).
- Low idle power. Document C-states, NIC/PCIe effects and before/after wall-power measurements.
- Xeon Broadwell E5 v4 nodes and DDR3 ECC, potentially 256 GiB. Some nodes may be single socket; verify real hardware.
- PCIe GPU pass-through must work; no requirement for live VM migration. vGPU sharing is exploratory and hardware-dependent.
- 25/40/56 Gb network adapters for short dedicated server interconnects. Tailscale is management, not the dataplane. Local 10GbE client connectivity remains a separate plan.
- Remote-first configuration and an automated, per-host installer; minimize keyboard work at the rack.

## Boot media and host

Use a dedicated, explicitly identified OS SSD. The initial `direct` autoinstall layout consumes the chosen disk's partition space, regardless of how little filesystem capacity the OS initially uses. VM datastore disks stay untouched. Future custom layout can limit root to 24-32 GiB if needed; do not improvise it during first deployment.

KVM/QEMU/libvirt and OVMF on the host. Use libvirt default NAT for first VM smoke tests. Native bridge/VLAN, SR-IOV, local block storage or shared filesystem networks follow only after an interface inventory and a connectivity plan.

## Interfaces and isolation

1. **Management:** existing Ethernet plus Tailscale to frontend and administrators; SSH, API via tailnet ACL.
2. **Guest traffic:** separate bridge or VLAN after NIC selection; no disruptive reparenting of management NIC during bootstrap.
3. **Storage/data/RDMA:** direct peer links or dedicated uplinks. IPoIB and RoCE may have different setup requirements and depend on NIC firmware and mode.
4. **Passthrough:** select actual PCI addresses and verify full IOMMU groups. Bind specific devices with `driverctl` only after approval.

## Reboot and performance policy

Leave CPU isolation, huge-page reservations, SR-IOV VFs, VFIO overrides and NIC mode changes unset by default. Record the future kernel parameters before a planned maintenance reboot. IOMMU kernel args and BIOS settings should ideally be done before first operational VMs, then measured.
