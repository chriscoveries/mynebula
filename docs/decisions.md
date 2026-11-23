# Decision log

Last reviewed: 2026-11-23.

| Area | Current choice | Rationale / revisit trigger |
| --- | --- | --- |
| Repo | chriscoveries/mynebula | Docs and scripts as agent handoff |
| Host OS | Ubuntu Server 26.10 amd64 | Linux 7.3 required; nine-month lifecycle, upgrade plan needed before July 2027 |
| Virtualization | QEMU/KVM with libvirt | OpenNebula node target and direct GPU passthrough |
| Orchestrator | OpenNebula 7.4 CE later | Remote webclip frontend; dedicated compatibility test required |
| OpenNebula support | Experimental on host 26.10 | Supported nodes list Ubuntu 24.04/26.04, Debian 12/13 |
| Installer | Per-node remastered ISO; user-data via Subiquity | Minimal local work after USB boot, destructive only with explicit target |
| Console access | SSH + out-of-band fallback | Headless GPU-less hardware possible; never make management dependent on VFIO GPU |
| Overlay | Tailscale | Private SSH/control traffic; 26.10 package repository exists |
| Guest networking | libvirt default NAT initially | Add bridges and VLANs after NIC confirmation |
| GPU | Conventional PCIe passthrough first | No live migration requirement; vGPU deferred |
| RDMA | Package/tool support only initially | Actual transport/IPoIB/RoCE and firmware must be inspected |
| Storage | Dedicated OS SSD; no swap file by default | Guest storage separate and adaptable |
| Memory | Preserve NUMA topology | Test CPU pinning/huge pages when guest workloads are defined |
| Power | Measure wall idle/load | Avoid adding NICs or VFs that prevent package C-states |

## Outstanding choices before physical installation

- Which precise SSD serial is the OS target for each node?
- Which NIC remains the management connection throughout boot/network changes?
- BIOS virtualization/VT-d status, UEFI vs legacy boot, Secure Boot policy and console fallback.
- Per-node hostname and SSH public key, plus a local recovery password hash.
- Tailscale token enrolment mode. One-use token on ISO provides zero touch but persists in install records/media; safer manual enrolment is possible.
- VM datastore scheme: local file, LVM thin, ZFS, btrfs, shared NFS or another later design.
- One-on-26.10 integration result before claiming the host can be managed by OpenNebula.

## Libvirt authorization note

Ubuntu 26.10 includes libvirt 12.6 and polkit-based socket access. OpenNebula's documented oneadmin/libvirt-group arrangement must be proven or adapted in a disposable test node before production; see docs/compatibility.md.
