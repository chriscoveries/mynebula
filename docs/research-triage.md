# Research triage (Devin web-research rounds, 2026-11-23)

Every claim from the research rounds, checked against the installed OpenNebula 7.4.1 tree, a live node (Dell Precision 7550, Ubuntu 26.04, kernel 7.0) and measurements.
Status: **DONE** (applied and verified) · **VERIFIED** (true, not yet applied) · **WRONG** (contradicted by evidence) · **OPEN** (unverified or needs a test) · **SKIP** (not for us now).

## 1. Power monitoring
| Claim | Status | Evidence / action |
|---|---|---|
| Official OpenNebula Prometheus stack (`opennebula-prometheus` + `-kvm`) is the premade path | DONE | Prometheus, Alertmanager, opennebula/node/libvirt exporters; 5 targets up; 90 d / 4 GB retention |
| The frontend package includes Grafana | WRONG | It ships dashboards only; Grafana is separate (not installed; Beszel is the dashboard) |
| The exporter unit is in `opennebula-prometheus` | WRONG | `opennebula-exporter.service` ships in `opennebula-prometheus-kvm`; install both on the frontend |
| node_exporter RAPL gives host watts once `energy_uj` is readable | DONE | udev rule 0444; idle 4.6 W, 1 h average 6.6 W |
| `psys` (whole-board) is exported | WRONG | node_exporter only exports package zones; psys (~5 W idle) is read by hand. OPEN: textfile collector |
| Per-VM watts: none built in; Kepler/Scaphandre | VERIFIED | Not needed yet |

## 2. GPU idle power under vfio-pci (Quadro RTX 3000, Turing mobile)
| Claim | Status | Evidence / action |
|---|---|---|
| vfio-pci runtime PM since 5.19; D3cold needs ACPI `_PR3` | VERIFIED | With host drivers, all 4 functions and the root port reach D3cold, so the firmware supports it |
| Main risk is the D3cold→D0 wake failing at the next VM start; fallback `disable_idle_d3=1` | OPEN | Live test planned (driver_override, wake cycles, dead-man reboot); needs someone near the laptop |
| Bind all 4 functions (one IOMMU group); USB-C on the GPU is lost to the host | VERIFIED | Group 1 = 01:00.0–.3 + root port only |
| LXC could use the GPU with the host driver instead of passthrough | OPEN | Raised 2026-11-23; test whether D3cold still holds |

## 3. Host-local image storage
| Claim | Status | Evidence / action |
|---|---|---|
| `TM_MAD=local` + `BRIDGE_LIST` keeps images on the host and clones host-local | WRONG | `tm/local/clone` always tars from the frontend host; the first VM failed |
| `TM_MAD=shared` image DS + shared system DS, both on the node | DONE | `shared/clone` rebuilds the source path under the node's own datastore root; VMs deploy |
| A symlink for a custom host path | DONE | `datastores/<id>` -> `/srv/one-images`; create it BEFORE `onedatastore create` |
| Import from URL lands only on the bridge host | DONE | Image bytes on the node; the frontend keeps metadata |

## 4. zram
| Claim | Status | Evidence / action |
|---|---|---|
| Not on by default in 24.04/26.04 server/cloud images | DONE (also 26.10) | 26.10 cloud image tested: no zram, no swap |
| `systemd-zram-generator` + config enables it | DONE, with a fix | The 24.04 cloud kernel lacks the zram module: add `linux-image-extra-virtual` |

## 5. RDMA
| Claim | Status | Evidence / action |
|---|---|---|
| virtio-rdma is RFC-only upstream | VERIFIED (doc) | Skip |
| soft-RoCE (rxe) in guests for functional tests now | OPEN | Phase A test: 2 VMs, rping/ib_send_bw |
| Real path: ConnectX-5/6 SR-IOV VFs via vfio; RoCEv2 over DAC, MTU 9000 | VERIFIED (doc) | Hardware not bought; see gpu-rdma.md |

## 6. OpenNebula 7.4 features and defaults
| Claim | Status | Evidence / action |
|---|---|---|
| Firecracker driver removed (6.10); hypervisors are KVM + LXC | VERIFIED | `remotes/vmm` = kvm, lxc only. Owner: "Firecracker's features, not Firecracker" |
| LXC driver for lite guests | VERIFIED + constraint | `opennebula-node-lxc` CONFLICTS with `opennebula-node-kvm`, so an LXC host VM is needed on KVM nodes |
| KSM via ksmtuned | DONE, differently | Kernel 7.0 KSM scan-time advisor (no ksmtuned), persisted by tmpfiles; with one VM: 33k pages shared, ~130 MB profit |
| Free page reporting: no toggle, maybe RAW | DONE | RAW with `VALIDATE=NO` (schema validation rejects it otherwise) gives one memballoon with freePageReporting='on'; fill/free 3 GB: RSS 3.4 GB -> 0.9 GB in 15 s |
| `MEMORY_RESIZE`/`MAX_MEMORY`, host `RESERVED_MEM` overcommit | OPEN | Needs host swap/zram before overcommitting |
| Memory snapshots as a warm pool | OPEN | Test resume time |
| `AUTOSTART` is a host attribute | WRONG (form) | It's the shipped hooks `hooks/autostart/{host,vm}` + `AUTOSTART=YES` on the VM. DONE, survived a host reboot |
| Marketplaces (OpenNebula, Linux Containers, DockerHub, TurnKey) | VERIFIED (doc) | Export only to the node image DS (DS 1 on the frontend can't deploy) |
| `QCOW2_OPTIONS` compression, image cache | OPEN | Cache matters at 2+ nodes |
| Backups: restic backup DS | OPEN | Candidate default; needs a target |
| Terraform provider maintained; no Packer, no GARM/Actions provider | VERIFIED (doc) | CI = cifast's GARM drives Incus inside a KVM VM (done: ci-7550) |
| PCI monitoring, TOPOLOGY pinning, host hooks, alert rules, OneKE | OPEN / SKIP | Alert rules next; OneKE at 2+ nodes |

## Round 2 (source-cited, OpenNebula one-7.4 tree)
| Claim | Status | Evidence / action |
|---|---|---|
| The KVM driver never emits `<memballoon>`; RAW is written at domain top level (LibVirtDriverKVM.cc:2782-2796), so a second `<devices>` | VERIFIED (source) | True as source facts |
| ...therefore freePageReporting is impossible in 7.4 | WRONG (practice) | libvirt 12 merges the RAW `<devices>`: the live domain has ONE memballoon with freePageReporting='on'; 3.4 GB -> 0.9 GB RSS measured. Depends on libvirt merge behaviour: re-test after libvirt upgrades |
| LXC driver has snapshot/save/restore/migrate actions; needs cgroup v2 delegation, AppArmor, bindfs in a guest | VERIFIED (source) / OPEN (test) | LXC host VM pending owner go |
| `MEMORY_MAX` + `MEMORY_RESIZE_MODE=HOTPLUG` = DIMM hotplug (not virtio-mem); otherwise balloon `currentMemory` | VERIFIED (source) | Candidate for overcommit with free page reporting |
| `RESERVED_MEM` host/cluster attribute; negative handling unverified | OPEN | Test before overcommitting; host zram/swap first |
| Clone-from-running-memory not exposed by oned | VERIFIED | SKIP; use system snapshots, measure resume |
| opennebula-node-exporter runs with no flags | VERIFIED (source) | psys needs a textfile collector |
| node_exporter has no hwmon collector; temps need a textfile collector | WRONG | Default hwmon collector already exports 92 series (coretemp, NVMe) |
| restic backup DS bundled (SFTP default or S3); a tailnet SFTP target works | VERIFIED (source) | Candidate default; pick a target (claw/firestar disk) |

## Round 3 (2026-11-23 15:41Z; tested 15:45Z; advisor consulted)
| Claim | Status | Evidence / action |
|---|---|---|
| Negative `RESERVED_MEM` allows scheduler overcommit (HostShare.cc:162-195, no sign check) | VERIFIED, NOT ADOPTED | `RESERVED_MEM=-8388608` (KB) took MAX_MEM from 64.16 to 72.54 GB; reverted. Prerequisites: host zram/swap (the node has none) and real demand (12 of 61 GB allocated). Accounting only: the kernel OOM-killer is the real limit |
| restic backup DS bundled (`DS_MAD=restic`, SFTP/S3, bundled binaries, incremental) | OPEN | Needs a target box (owner decision). Test on a throwaway VM only; repo password stays out of git |
| LXC host VM in a 26.04 guest needs AppArmor userns relief + cgroup v2 `Delegate=yes` + subuid/subgid | OPEN | First check `lxcrc` for privileged vs unprivileged. Before enrolling ANY second host, put nebula-7550 + DS 101/102 in their own cluster: those shared-TM paths exist only on that node |

## Verified runtime notes
- **30 W cap drift:** exactly one rewrite in 40 min (200 W / 75 W / 135 W right after boot), so it's a boot-time reset and the 1-minute timer is enough.
- **`scripts/apply-host-policy.sh`:** ran end to end on nebula-7550 (2026-11-23); idempotent; live values unchanged.

## Round 4 (2026-11-23 15:52Z; LXC host VM built and tested; advisor consulted)
| Claim | Status | Evidence / action |
|---|---|---|
| LXC driver is unprivileged by default (opennebula_vm.rb:243) | VERIFIED, with a catch | True for the driver, but the Linux Containers marketplace templates set `LXC_UNPRIVILEGED="false"`. Set "yes" on every exported template (done on template 2) |
| AppArmor `apparmor_restrict_unprivileged_userns=1` blocks LXC in a guest | NOT APPLICABLE | Root starts the containers; unprivileged worked with the restriction on (uid_map 0 600100001 65536) |
| cgroup v2 delegation needed | NOT NEEDED | Limits enforced: `memory.max` = MEMORY, `cpu.weight` from CPU. `free` in a container shows host-VM memory (no lxcfs), display only |
| CONTEXT works in LXC | VERIFIED | Hostname, SSH key and static IP applied |
| Nested restart (LXC host VM reboot) | VERIFIED | The autostart hook resumed the container about 3 min after `lxc-7550` rebooted; Tailscale and lxcbr0 came back |
| lxc-net DHCP overlapping the OpenNebula address range | FIXED | `LXC_DHCP_RANGE=10.0.3.2,10.0.3.99` (the image's netplan also takes a DHCP lease; it now lands outside 100-199) |
| Prometheus rules.yml contents; Alertmanager routing | PARTLY DONE | rules.yml is loaded (4 groups, 12 rules). Alertmanager's only receiver is the default `web.hook` at 127.0.0.1:5001 (nothing listens), so alerts go nowhere until the owner picks a destination |
| `SchedulerDown` fires permanently | FIXED LOCALLY (upstream bug) | 7.4 runs the scheduler inside oned (`one_sched.rb`), but opennebula_server_collector.rb:41 checks the removed `opennebula-scheduler.service`. rules.yml now alerts only if the exporter itself is down (original kept as rules.yml.orig-20261123). Report upstream |
| `QCOW2_OPTIONS="-o compression_type=zstd"` on shared TM | OPEN | Measure space saved and read cost on a throwaway image |
| Beyond: OneGate, VM groups/affinity, quotas, host hooks, OneFlow | OPEN (ranked) | Host hooks first (GPU D3cold) |
| patch_datasources.rb adds a libvirt exporter target for every host | FIXED LOCALLY | It raised a critical InstanceDown for lxc-7550:9926 (no libvirt on an LXC host). Removed that target from prometheus.yml; re-running patch_datasources.rb re-adds it, so remove it again after any re-run |
