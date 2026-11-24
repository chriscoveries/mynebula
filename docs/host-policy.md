# Host policy: defaults for every mynebula node

Owner decisions, 2026-11-23. `scripts/apply-host-policy.sh` applies them and is safe to re-run on any node.

## Power
- **Laptop-class hosts** (a battery is present). Owner's goal: QUIET, not cool.
- **CPU package cap: 30 W, written to the MSR interface only** (`intel-rapl:0`, long and short term).
  - Proven to bind on its own: an all-core burst averaged 29.97 W with thermald moving the MMIO limit, vs 29.95 W with both pinned.
  - thermald (`--adaptive`, Dell DPTF) owns the MMIO limit; leave it alone. It also resets MSR to 200 W when it starts.
  - So a watchdog timer re-applies MSR every minute (`OnCalendar=*:*:00`; the service is stopped before enabling; install fails if the timer has no next run).
  - **Per-host override:** `/etc/mynebula/host.env` (`CPU_CAP_W=<watts>`), read by apply-host-policy.sh. nebula-7550 uses `CPU_CAP_W=20`, chosen by the quiet-cap sweep.
- **Turbo off** (`intel_pstate/no_turbo=1`, persisted via `/etc/tmpfiles.d/mynebula-no-turbo.conf`). Owner 2026-11-23: turbo bursts spike the package ~65→100 °C within seconds and start the fans. Max 2.6 GHz; idle floor 800 MHz (powersave governor).
- **Servers and desktops** (no battery): no cap. Set `CPU_CAP_W` explicitly if wanted.
- **Laptops also get:**
  - charge held at 75–80 %;
  - Wi-Fi power save off and the Dell **quiet** platform profile (owner 2026-11-23: fans stay at 0 rpm at idle; `cool` ran fans at 3800 rpm for 2 °C less; the 30 W cap bounds heat);
  - logind ignores the lid and sleep targets are masked;
  - shutdown below 10 % battery.
- RAPL `energy_uj` is made world-readable (udev) so the Prometheus node exporter can report watts.

## Memory: lite, deduplicated guests ("Firecracker features on KVM")
- **KSM** on, with the kernel scan-time advisor (`advisor_mode=scan-time`, `advisor_max_cpu=10`, target scan 200 s), `use_zero_pages=1`, `smart_scan=1`.
  - Trade-off: KSM shares identical pages across guests, which is a known cross-VM timing side channel. Accepted for this lab.
- **KSM on laptops: slow scan** (`advisor_mode=none`, `pages_to_scan=100`, `sleep_millisecs=200`). ksmd drops from ~10 % to ~0.2 % CPU, fewer fan starts. Servers keep the scan-time advisor.
- **EPP on laptops: `balance_power`** (tmpfiles, all CPUs): lazier ramp-up on bursts, fewer fan starts, no measurable clock cost.
- **Guest RAM** is allocated on touch (no hugepage preallocation).
- **Free page reporting** on every VM template, so freed guest memory returns to the host:
  `RAW=[TYPE="kvm", DATA="<devices><memballoon model='virtio' freePageReporting='on'/></devices>", VALIDATE="NO"]`.
  OpenNebula 7.4 has no toggle; with `VALIDATE=NO`, libvirt ends up with a single balloon device carrying the flag.
  Measured: a guest that filled and freed 3 GB went from 3.4 GB host RSS back to 0.9 GB within 15 s.
- **qemu-guest-agent in every guest** plus `FEATURES=[GUEST_AGENT="yes"]` in every template: OpenNebula re-syncs the guest clock on resume through it. Without it, guests took ~2 min to answer after a resume (measured).
- **zram in every guest:** `systemd-zram-generator`, zstd, min(RAM/4, 8 GB). Ubuntu cloud images ship neither zram nor swap, and the 24.04 cloud kernel needs `linux-modules-extra` (pull in `linux-image-extra-virtual` so kernel updates keep zram).

## Storage
- **Disk layout:** 1 GB EFI, 32 GB root, and the rest as an ext4 data partition at `/var/lib/one/datastores`.
- **Base images:** image datastore `base-images`, with `TM_MAD=shared` and `BRIDGE_LIST=<node>`, symlinked to `/srv/one-images` on the node root.
- **VM disks:** system datastore `system-<node>`, with `TM_MAD=shared`, on the data partition.
- **Why not `TM_MAD=local`:** its clone always copies from the frontend, so it can't serve an image that lives only on the node.
- **Base image import (zstd):** convert on the node (`qemu-img convert -c -O qcow2 -o compression_type=zstd`), serve it over a temporary tailnet-only HTTP server on the node, and `oneimage create --path http://<node>:<port>/<file>`. The bytes never land on the frontend, and zstd reads ~2.3x faster than Ubuntu's zlib at the same size.
- **Thin provisioning:** OS disks are qcow2 overlays on the base image, volatile disks are sparse raw files, and `discard=unmap` is passed through to guests.

## Networking
- **VM network:** a NAT network on libvirt's `virbr0`, with OpenNebula `VN_MAD=dummy` so OpenNebula never deletes the bridge. VMs are reached over Tailscale inside the guest.
- **Name resolution:** the node resolves the frontend by name through an `/etc/hosts` entry with its tailnet IP.

## Lifecycle
- **Autostart:** the OpenNebula autostart hooks (`autostart-host`, `autostart-vm`) are installed on the frontend, and VMs and templates carry `AUTOSTART=YES`. **Exception:** the on-demand inference VM must NOT carry it. The proxy's `onevm poweroff` is not undone by the hook (it resumes only VMs the monitor found off), but any stop the monitor detects (a shutdown from inside the guest, a killed QEMU) is resumed ~1.5 min later [M]. **To keep an AUTOSTART VM off, power it off through OpenNebula, never from inside.** Tested: a VM came back by itself after a host reboot.

## Containers
- **LXC is preferred** for trusted Linux services.
- **Owner rule (2026-11-24): no strangers' code in LXC.** Containers share the host kernel, so anything that builds or runs untrusted code (CI runners, user uploads, internet-facing risky services) goes in a KVM VM. KVM is also used for hardware passthrough (GPU), non-Linux or different-kernel guests, and whole-VM suspend/power-off.
- **Constraint:** `opennebula-node-lxc` conflicts with `opennebula-node-kvm`, so LXC runs in an OpenNebula-managed **LXC host VM** on KVM nodes, in its own cluster. See docs/lxc-host-vm.md.
- **Container defaults:** unprivileged (`LXC_UNPRIVILEGED="yes"`, overriding the marketplace's "false"), `AUTOSTART=YES`, and lxc-net DHCP kept below the OpenNebula address range.

## Monitoring
- **Node:** OpenNebula Prometheus exporters (`opennebula-prometheus-kvm`: node and libvirt exporters).
- **Frontend:** Prometheus and Alertmanager on the frontend (`opennebula-prometheus`), with 90-day / 4 GB retention, tailnet only.
- **Whole-platform power:** the RAPL `psys` zone is exported as `mynebula_rapl_psys_joules_total` through the node_exporter textfile collector, because node_exporter's rapl collector skips psys.
- **Temperatures** come from node_exporter's default hwmon collector.
- **Beszel:** the hub is on the frontend (webclip). Each node runs the pinned cifast runbook agent (`beszel.sh install --role agent --listen-ip <tailnet ip>`) and is registered in the hub.
