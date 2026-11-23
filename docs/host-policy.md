# Host policy: defaults for every mynebula node

Owner decisions, 2026-11-23. `scripts/apply-host-policy.sh` applies them and is safe to re-run on any node.

## Power
- **Laptop-class hosts** (a battery is present): CPU package capped at **30 W** with RAPL (both `intel-rapl:0` and `intel-rapl-mmio:0`, long and short term).
  - A 1-minute timer (`mynebula-cpu-cap.timer`) re-applies it, because thermald and firmware rewrite the limits after boot (seen on a Dell Precision 7550: 200 W / 75 W at boot).
  - Measured on an i7-10750H: 1–2 busy threads are unaffected (~3.7 GHz at 14–20 W); all-core settles at ~2.8 GHz at 29 W.
- **Servers and desktops** (no battery): no cap. Set `CPU_CAP_W` explicitly if wanted.
- **Laptops also get:**
  - charge held at 75–80 %;
  - Wi-Fi power save off and the balanced platform profile;
  - logind ignores the lid and sleep targets are masked;
  - shutdown below 10 % battery.
- RAPL `energy_uj` is made world-readable (udev) so the Prometheus node exporter can report watts.

## Memory: lite, deduplicated guests ("Firecracker features on KVM")
- **KSM** on, with the kernel scan-time advisor (`advisor_mode=scan-time`, `advisor_max_cpu=10`, target scan 200 s), `use_zero_pages=1`, `smart_scan=1`.
  - Trade-off: KSM shares identical pages across guests, which is a known cross-VM timing side channel. Accepted for this lab.
- **Guest RAM** is allocated on touch (no hugepage preallocation).
- **Free page reporting** on every VM template, so freed guest memory returns to the host:
  `RAW=[TYPE="kvm", DATA="<devices><memballoon model='virtio' freePageReporting='on'/></devices>", VALIDATE="NO"]`.
  OpenNebula 7.4 has no toggle; with `VALIDATE=NO`, libvirt ends up with a single balloon device carrying the flag.
  Measured: a guest that filled and freed 3 GB went from 3.4 GB host RSS back to 0.9 GB within 15 s.
- **zram in every guest:** `systemd-zram-generator`, zstd, min(RAM/4, 8 GB). Ubuntu cloud images ship neither zram nor swap, and the 24.04 cloud kernel needs `linux-modules-extra` (pull in `linux-image-extra-virtual` so kernel updates keep zram).

## Storage
- **Disk layout:** 1 GB EFI, 32 GB root, and the rest as an ext4 data partition at `/var/lib/one/datastores`.
- **Base images:** image datastore `base-images`, with `TM_MAD=shared` and `BRIDGE_LIST=<node>`, symlinked to `/srv/one-images` on the node root.
- **VM disks:** system datastore `system-<node>`, with `TM_MAD=shared`, on the data partition.
- **Why not `TM_MAD=local`:** its clone always copies from the frontend, so it can't serve an image that lives only on the node.
- **Thin provisioning:** OS disks are qcow2 overlays on the base image, volatile disks are sparse raw files, and `discard=unmap` is passed through to guests.

## Networking
- **VM network:** a NAT network on libvirt's `virbr0`, with OpenNebula `VN_MAD=dummy` so OpenNebula never deletes the bridge. VMs are reached over Tailscale inside the guest.
- **Name resolution:** the node resolves the frontend by name through an `/etc/hosts` entry with its tailnet IP.

## Lifecycle
- **Autostart:** the OpenNebula autostart hooks (`autostart-host`, `autostart-vm`) are installed on the frontend, and VMs and templates carry `AUTOSTART=YES`. Tested: a VM came back by itself after a host reboot.

## Containers
- **LXC is preferred** for trusted Linux services.
- **Full KVM VMs are for:** untrusted code (CI), own-kernel needs, and hard isolation.
- **Constraint:** `opennebula-node-lxc` conflicts with `opennebula-node-kvm`, so LXC runs in an OpenNebula-managed **LXC host VM** on KVM nodes.

## Monitoring
- **Node:** OpenNebula Prometheus exporters (`opennebula-prometheus-kvm`: node and libvirt exporters).
- **Frontend:** Prometheus and Alertmanager on the frontend (`opennebula-prometheus`), with 90-day / 4 GB retention, tailnet only.
- **Whole-platform power:** the RAPL `psys` zone is exported as `mynebula_rapl_psys_joules_total` through the node_exporter textfile collector, because node_exporter's rapl collector skips psys.
- **Temperatures** come from node_exporter's default hwmon collector.
- **Beszel:** the hub is on the frontend (webclip). Each node runs the pinned cifast runbook agent (`beszel.sh install --role agent --listen-ip <tailnet ip>`) and is registered in the hub.
