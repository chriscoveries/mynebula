# MyNebula

Documentation-first project for reproducible, low-touch installation of Ubuntu 26.10 KVM hypervisor nodes, with a future OpenNebula 7.4 management frontend on `webclip`.

**Status: initial design and installer work in progress; no hardware deployed.**

## Goals

- Boot a per-node Ubuntu Server 26.10 USB image, install the OS on an explicitly selected disk, then complete first-boot configuration.
- Deploy native KVM/QEMU/libvirt, baseline VFIO and RDMA tooling, and Tailscale access.
- Prepare for GPU passthrough and OpenNebula enrolment, preserving compatibility checks.
- Keep configuration, decisions, scripts, validation and agent handoff in this repo.
- Limit repeated manual work at the physical host; use an agent once each node is reachable.

## Important compatibility constraint

OpenNebula 7.4 lists Ubuntu **24.04 and 26.04 LTS** for its KVM node packages. Ubuntu **26.10** (Linux 7.3) is a desired experimental host OS and must pass an integration test before OpenNebula host packages are installed. Do not add a 26.04 package repository to a 26.10 node merely to bypass this restriction.

## Work order

1. Read [AGENTS.md](AGENTS.md) and [architecture](docs/architecture.md).
2. Review [decisions](docs/decisions.md) and [safety constraints](docs/security.md).
3. Collect host inventory using [preflight](scripts/preflight.sh), and confirm the specific OS disk serial.
4. Render a per-host [autoinstall config](docs/installer.md), then build an ISO and test it in a disposable VM.
5. Deploy and validate the bare-metal KVM host.
6. Test OpenNebula integration separately. The frontend on `webclip` is deferred.

## Repository layout

- `AGENTS.md` : operative handoff for a server-side agent
- `docs/` : architecture, deployment, networking, storage, validation and decisions
- `scripts/` : small, inspectable provisioning and audit utilities
- `tests/` : non-destructive configuration checks

No tokens, private SSH keys, passwords or generated per-host images belong in Git. An unattended installation can erase disks; the agent must obtain an explicit target-disk approval before deploying an image.

## Upstream documentation

- [Ubuntu 26.10 release notes](https://documentation.ubuntu.com/release-notes/26.10/)
- [Ubuntu autoinstall specification](https://canonical-subiquity.readthedocs-hosted.com/en/latest/reference/autoinstall-reference.html)
- [OpenNebula 7.4 KVM node](https://docs.opennebula.io/7.4/software/installation_process/cluster_installation/kvm_node_installation/)
- [OpenNebula 7.4 platform notes](https://docs.opennebula.io/7.4/software/release_information/release_notes/platform_notes/)

## Compatibility watch

Ubuntu 26.10 ships libvirt 12.6 with polkit-based socket access; OpenNebula's 7.4 Ubuntu guide still expects group-based access for oneadmin. See [compatibility risks](docs/compatibility.md) for the required proof-of-concept. CI unit tests validate scripts, not a full ISO boot.
