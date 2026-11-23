# mynebula findings (concise)

Lab: frontend webclip (OpenNebula 7.4.1); node nebula-7550 (Dell Precision 7550, Ubuntu 26.04 now, 26.10 later per owner).
Tags: **[M]** measured here · **[S]** from source/docs only, not run here · **[E]** estimate.
Detail: [research-triage.md](research-triage.md) · Defaults: [host-policy.md](host-policy.md) · LXC: [lxc-host-vm.md](lxc-host-vm.md).
Updated 2026-11-23 19:45Z; the loop updates this when a headline figure changes. Work status and to-do list: [deployment-status.md](deployment-status.md).
**Note:** performance figures taken before 19:33Z were measured with turbo ON (cold start, wake proxy, suspend/resume, CI benchmark, RDMA/TCP, zstd reads). Turbo is now OFF (owner), so re-measure any that matter.

## Bottom line
1. **Running today:**
   - One laptop node serving cifast's CI VM (ci-2604) and an LXC host (lxc-7550).
   - Thin disks, KSM, free page reporting, zram, autostart and power monitoring are all on [M].
2. **"Firecracker features" on KVM work** [M]: memory dedupe saves GBs, freed RAM returns in seconds, suspend/resume preserves processes, and containers start in seconds.
3. **GPU, recommended shape:** a small on-demand inference VM that's off when idle [S]. The live passthrough test still needs someone on site.
4. **Owner decisions:** the quiet cap (after the sweep), Tailscale keys, backup target, alert destination, GPU shape + wake-proxy graduation, an on-site slot, PR to main.

## The node
- **CPU** i7-10750H 6C/12T [M].
- **RAM** 2×32 GB DDR4 SODIMM (Samsung M471A4G43AB1-CWE, rated 3200 CL22) running at **2933 MT/s**, dual channel [M]. Timings at 2933 were not read; JEDEC suggests ~CL21 ≈ 14 ns [E] (`decode-dimms` would confirm). 2 of 4 slots free; 128 GB max [M].
- **NVMe** 1 TB: 32 GB root, 920 GB VM data [M].
- **GPU** Quadro RTX 3000 Mobile 6 GB [M].
- **Network:** Wi-Fi main link; Tailscale; uplink 33 Mbit/s, downlink 232 Mbit/s [M].

## Power
- **Cap:** CPU package capped at 30 W, laptops only [M].
  - thermald (`--adaptive`) is the only writer of the MMIO limit (48–75 W) and resets MSR to 200 W when it starts [M]. A 1-minute watchdog re-applies the MSR cap. It silently stopped firing for 2.7 h on 23 Nov (stale unit state) and was fixed: verify timers by their next run, not by the value they set.
  - The timer has not yet been through a reboot.
- **The cap binds through the MSR limit alone** [M]: all-core burst mean over seconds 5–20 was 29.97 W with thermald moving the MMIO limit (48–75 W), vs 29.95 W with both pinned at 30 W. So the cap script writes only `intel-rapl:0`, on an `OnCalendar` 1-minute watchdog; the MMIO limit is left to thermald. D1's 40 W peak was a sampler artifact.
- **Temperature spikes, not average heat:** the package temperature swings ~65↔100 °C within seconds even at 10–15 W, and hits 100 °C at 30 W even with fans on `cool` [M]. This pattern is often a sign of poor heatsink contact; only opening the laptop would tell [E].
- **Turbo OFF since 19:33Z (owner):** max 2.6 GHz, idle 800 MHz [M]. Before that, under the cap: 1–2 threads ~3.7 GHz, all-core ~2.8 GHz at 29 W [M]. Single-thread is now ~30 % slower [E].
- **Draw:** platform (psys, as firmware reports it) ~5 W idle, 26 W with CI busy; CPU ~3 W idle [M]. Wall power not measured.
- **Fans:** Dell firmware profile `quiet` (owner's choice) [M]:
  - Fans are off at idle. `balanced` is also 0 rpm at idle, holds ~2,300 rpm under load, and is not cooler: both averaged ~82 °C under CI load and both hit 100 °C and throttle in bursts.
  - `cool` runs ~3,800 rpm.
  - Nothing in Linux writes the fans; the firmware cycles them. thermald (`--adaptive`) is the only writer of the MMIO power limit.
  - Manual PWM is exposed but not used (unsafe unattended).
- **Quiet setup (adopted 23 Nov):** `quiet` + turbo off + 20 W cap + KSM slowed + EPP balance_power. Silent at idle; under saturated load the fans run ~73 % of the time at 20 W (25 W: 94 %, 15 W: 55 %, 12 W: 0 % for 4 min at ~40 % less CPU) [M, one pass]. Table in research-triage.md.
- **Monitoring:** CPU package, psys and temperatures go to Prometheus on webclip; Beszel covers the physical hosts [M].

## Memory ("Firecracker features" on KVM)
- **KSM** (kernel auto-tuner): 5.0 GB saved; the host used 15 GB for 40 GB allocated (16:37Z, 3 VMs, one since terminated) [M]. Cost: ksmd uses a steady ~10 % CPU, a heat source; under review in the quiet-cap sweep [M].
- **Free page reporting:** a guest's freed 3 GB returned to the host in 15 s (3.4 → 0.9 GB) [M]. OpenNebula has no switch; it's set with RAW `VALIDATE=NO`, which relies on libvirt merging the device, so re-test after libvirt upgrades.
- **Thin RAM:** allocated on touch; zram in every guest [M].
- **Overcommit:** negative `RESERVED_MEM` raises schedulable memory [M]. Not adopted: the host has no swap.
- **Suspend/resume:** suspend 3.5 s; resume 7–15 s to RUNNING, **~23 s until SSH answers**; processes survive [M]. Needs qemu-guest-agent: without it, ~2 min [M].
- **Firecracker/LXD drivers:** not in 7.4, which has only KVM + LXC [M].

## Storage
- **Datastores:** `TM_MAD=shared`, node-local, in their own cluster; base images on the node root, VM disks on the data partition [M]. `TM_MAD=local` always copies from the frontend [M].
- **Thin:** OS disks are qcow2 overlays (a 40 GB disk ≈ 0.2 GB used); runner disks are sparse [M].
- **Compression:** Ubuntu cloud images ship zlib-compressed. zstd: same size, 2 GB sequential read 0.44 s vs 1.01 s (one run) [M].
  - **Adopted for new imports**: convert on the node, serve over a temporary tailnet HTTP server, register; the bytes never touch webclip; verified with a VM boot [M]. Existing images back live VMs, so they aren't touched.

## Lifecycle
- **Autostart:** OpenNebula autostart hooks + `AUTOSTART=YES`. A node reboot brought a VM back by itself (tested once); an LXC host VM reboot brought its container back (~3 min) [M].

## LXC
- **Placement:** runs in an LXC host VM, because `opennebula-node-lxc` conflicts with node-kvm; enrolled as a second host in its own cluster [M].
- **What works:** unprivileged containers (marketplace templates default to privileged, so override them), memory/CPU limits enforced, start in seconds [M].
- **Device passthrough** via `LXC_PROFILES` works (proven with /dev/fuse) [M].

## GPU (Quadro RTX 3000)
- **Idle:** with host drivers it's fully off (D3cold) most of the time [M].
  - OpenNebula's PCI probe wakes it ~16 s per run (every 600 s).
  - Total awake time: 4.8 % over a busy 30 min. The wakes come from that probe and from VM lifecycle events (create/poweroff/start/terminate, ~11 s each); nothing else [M].
- **OpenNebula sees all 4 functions** (one IOMMU group) [M]. UEFI guests boot [M].
- **Passthrough (not run here):**
  - All 4 functions to one VM; libvirt binds vfio at VM start, no reboot [S].
  - A GPU VM has all its RAM pinned (no balloon, free page reporting or KSM) [S].
  - In a guest the GPU likely reaches only D3hot [S].
- **Recommended shape:** a small on-demand inference VM serving an API, off when idle, so the GPU returns to D3cold [S].
  - **Wake proxy prototype works** [M]: llama-swap on the frontend wakes the powered-off VM through a restricted OpenNebula user. Cold 36-54 s, warm 0.65 s, idle power-off 10-15 s after the timeout (scripts/inference-wake/). Not production-ready: a killed proxy leaves the VM running, so it needs a reaper.
  - A VM holding the GPU **cannot be suspended** (QEMU vfio migration blocker; libvirt hostdev; OpenNebula `save` = `virsh save`) [S]. So idle = **poweroff**. Cold start measured on CPU (no GPU), 8 GB UEFI 26.04 VM, qwen2.5:7b Q4: RUNNING 8.3 s, SSH 25.7 s, Ollama API 30.6 s, **first answer 44.0 s** (model load 6.1 s) [M, one run]. With the GPU expect ~40–55 s [E]. The owner accepts 30–60 s.
  - Untested idea: guest-initiated suspend-to-RAM might let the GPU drop to a low-power state without OpenNebula involvement.
  - The GPU-in-LXC-host alternative would keep the GPU awake [S].

## CI
- **ci-2604:** Ubuntu 26.04; 8 vCPU / 12 GB / 40 GB + 80 GB raw. Serves cifast's runners via claw's GARM; benchmark 68.6 s vs 67.8 s on the old VM (per cifast).
- **Uplink:** 33 Mbit/s, so the VM reads the build cache only and never pushes artifacts.

## RDMA
- **soft-RoCE between two VMs works but is slow** [M]: ~3–3.7 Gb/s (1–4 QPs), ib_write_lat ~26 us, rping OK. Plain TCP between the same VMs: 28–34 Gb/s. rxe is CPU-bound software, so use it for correctness only.
- **Real RDMA** [S]: ConnectX-5/6 SR-IOV VFs over DAC (RoCEv2, MTU 9000). No RDMA NIC in the node.

## Upstream bugs / gotchas
- **SchedulerDown:** the 7.4 exporter checks a removed `opennebula-scheduler.service`, so the alert fires forever (disabled locally) [M].
- **patch_datasources.rb** adds a libvirt target for LXC hosts too, giving a false InstanceDown [M].
- **lxc-net DHCP** overlaps the OpenNebula address range unless narrowed [M].
- **Installer stick:**
  - YUMI's `VentoyPart` crashes the storage probe [M].
  - Naming absent Wi-Fi interfaces makes netplan fail [M].
  - Both fixes are in the templates but not yet tested from the stick.

## Open
- **Owner:**
  - Tailscale: untagged devices with expiring keys; old key to revoke.
  - Backup (restic) target.
  - Alert destination.
  - GPU shape.
  - An on-site slot for the GPU test.
- **Unverified:**
  - Guest-initiated S3 with a GPU attached (power state while suspended).
  - The cap timer across a reboot.
