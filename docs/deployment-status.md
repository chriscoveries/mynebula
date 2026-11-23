# Deployment status

Updated: 2026-11-23 20:10Z. Facts and measurements: [FINDINGS.md](FINDINGS.md). Evidence per claim: [research-triage.md](research-triage.md).

| Item | Status | Evidence |
| --- | --- | --- |
| Frontend (OpenNebula 7.4.1 on webclip) | Deployed | oned/FireEdge/OneGate; Prometheus + Alertmanager; Beszel hub |
| KVM node nebula-7550 (Precision 7550, Ubuntu 26.04, kernel 7.0) | Deployed, ON | Enrolled via autoregister; reboot-tested; host policy applied (scripts/apply-host-policy.sh) |
| Datastores / clusters | Deployed | Shared-TM node-local DS (base images on root, VM disks on data); cluster per host |
| CI VM for cifast (ci-2604, 26.04) | Serving | claw's GARM drives it; replaced ci-7550 (terminated) |
| LXC host VM (lxc-7550) | Deployed, ON | Unprivileged containers, nested autostart tested; docs/lxc-host-vm.md |
| Memory features (KSM, free page reporting, zram, thin disks) | Deployed | Measured: KSM 5.0 GB saved; FPR 3.4 -> 0.9 GB |
| Power: 30 W MSR cap, turbo off, Dell quiet profile | Deployed | Cap proven to bind (29.97 W); turbo off in apply-host-policy.sh (laptops); quiet cap per host pending |
| Fan-start metric | Partial | Prometheus rule `node:fan_starts:per_hour` (lower bound, monitoring/fan-rules.yml); exact 2 s node counter queued |
| GPU passthrough (RTX 3000) | Planned, needs on-site | PCI monitoring + UEFI verified; live bind not done |
| Inference wake proxy | Prototype | scripts/inference-wake/; not production-ready |
| Installer stick (Ventoy/YUMI) | Needs v9 | See known issues |
| RDMA | Research + soft-RoCE only | No RDMA NIC |

## In flight
- **Quiet-cap sweep** on nebula-7550 (sys-devin-rt). Done: bursty turbo-off, KSM-throttled, EPP balance_power, 25 W. Running: 20 W, then 15 W and a 15-min soak. Then advisor validation, and the owner picks the cap.
- **Joint firestar window, 24 Nov 10:05Z:** cccc 0.4.60 fork candidate (cwflab), then set B package updates + reboot, only on the owner's GO and a green claw group-restore rehearsal. nebula-7550/webclip are unaffected.

## To do
- **Ours:**
  - an exact fan-start counter (node-side 2 s poller; queued after the sweep);
  - keep or delete test image 6 (26.04 zstd);
  - test the `onevm create` denial for the proxy user;
  - read how the autostart-vm hook treats an operator poweroff;
  - report the 7.4 exporter `SchedulerDown` bug upstream;
  - remove the stale ci-7550 tailnet device;
  - stick v9 (VentoyPart early-command test, Wi-Fi interface fix);
  - tell cifast the final cap AND that turbo is permanently off (their benchmark ran with turbo on).
- **Owner:**
  - pick the quiet cap;
  - Tailscale key expiry (nebula-7550, ci-2604, lxc-7550) + revoke the stick key;
  - restic backup target;
  - alert destination;
  - GPU shape + wake-proxy graduation;
  - an on-site slot for the GPU bind;
  - PR this branch to main.
- **On-site session:** GPU bind test, plus idle power with vfio vs host drivers. One scripted session with a dead-man reboot, at a time agreed with cifast.

## Next-reboot checklist (nebula-7550; needs a time agreed with cifast)
Cap watchdog fires (`list-timers` NEXT) and MSR = 30 W; `no_turbo=1`; profile `quiet`; RAPL `energy_uj` readable; psys exporter timer; KSM settings; PCI filter; ci-2604 and lxc-7550 come back by themselves (autostart).

## Known issues (2026-11-23)
- **Wi-Fi:** `scripts/render-ventoy-template.py` lists five Wi-Fi interface names (`WIFI_IFACES`). netplan apply fails when a named interface is absent (NETWORK_FAIL in the installer on the Precision 7550). The 7550 was installed with a config naming only its real interfaces (wlo1/eno2). Fix before the stick is used on another machine.
- **Live installer storage probe:** YUMI's `VentoyPart` dm device crashes the curtin storage probe. The early-command `dmsetup remove VentoyPart` is in the templates but not yet re-tested from the stick.
