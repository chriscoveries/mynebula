# MyNebula agent operating instructions

This repo is the authoritative plan for preparing Ubuntu 26.10 KVM hypervisors, then enrolling them into an OpenNebula 7.4 frontend hosted separately on `webclip`. The user wants docs first, compact auditable scripts, and the actual server work handed off to a separate agent.

## Operating contract

- Make durable changes as commits with a short rationale. Update the relevant docs when design or implementation changes.
- Default to read-only inspection. Installation, disk formatting, partitioning, BIOS changes, bootloader changes, service interruptions, reboot, Tailscale ACL changes, firewall changes and production OpenNebula package installation require explicit scope and approval from the user.
- Never boot an unattended/wiping ISO against a real machine before verifying that machine's exact OS-disk serial against the rendered config and obtaining approval.
- Do not commit keys, credentials, private IPs, customer information, generated autoinstall configs, build artefacts or inventory dumps with secrets. `.gitignore` covers common cases only.
- Keep the original management NIC and SSH access working. Preserve Tailscale access, remote-console fallbacks and a recovery path before touching networking or passthrough.
- Do not configure any primary display GPU, boot storage controller, management NIC or entire IOMMU group for VFIO without physical-device confirmation.
- Avoid forced ACS overrides, experimental GPU splitting, unsupported vGPU workarounds and automatic huge-page preallocation in initial deployment.
- Ubuntu 26.10 is outside OpenNebula 7.4's supported host OS matrix. Do not inject the 26.04 repository into a 26.10 host. Record experimental tests before any compatibility workaround.
- Report read-only checks, diffs and evidence. Do not invent successful deployment, benchmarks or hardware detection.

## First assigned work

1. Read `README.md`, `docs/architecture.md`, `docs/installer.md`, `docs/security.md` and `docs/validation.md`.
2. Confirm exact host specifications and BIOS/UEFI, disk, NIC, GPU and RDMA hardware through read-only `scripts/preflight.sh`.
3. Inspect installer output and CI, then run `python3 -m unittest discover -s tests -v`.
4. Run unattended installer in disposable QEMU VMs (UEFI and legacy BIOS if needed) with a disposable disk serial.
5. Confirm one-boot Tailscale enrollment with a one-use key in a disposable tailnet/test tag, or document the fallback; no real credential in Git.
6. Present the machine-specific install proposal and exact destructive targets for approval before touching bare metal.
7. After approved deployment, run `scripts/verify-node.sh`, capture redacted logs and update `docs/deployment-status.md`.
8. In a separate disposable VM, evaluate whether OpenNebula 7.4's node package supports the 26.10 libvirt userspace and kernel; present evidence and options before modifying production nodes.

## Acceptance criteria

A node boots with Ubuntu 26.10, uses the 7.3-series kernel, has working SSH, is reachable on Tailscale, runs KVM/libvirt, shows IOMMU groups where supported by firmware, and has functioning NIC/GPU inventory. RDMA is validated per actual hardware; VFIO binding and VM GPU passthrough are later explicit tests. Do not mark OpenNebula enrolment complete until the frontend exists and `onehost` status is ON.

## Agent deliverable

Submit a concise status: host name, OS/kernel, target disk serial, network reachability, CPU/IOMMU, KVM smoke test, GPU/NIC/RDMA probes, reboot count, SSH survivability, caveats, commands performed, changed files, commit/PR, next approval needed. Redact IPs/secrets where relevant.
