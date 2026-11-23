# Deployment status

Updated: 2026-11-23.

| Item | Status | Evidence |
| --- | --- | --- |
| GitHub repository | Initialised | README and design docs |
| Ubuntu 26.10 image build | Awaiting test | ISO builder is a starting point; require QEMU BIOS/UEFI proof |
| Native KVM/libvirt host | Not deployed | No physical target approved |
| Tailscale zero-touch | Proposed | Official 26.10 package repo; token-handling risk documented |
| GPU VFIO / IOMMU | Planning | Firmware and PCI grouping unknown |
| RDMA / peer links | Planning | Cards, firmware and link mode unknown |
| OpenNebula 7.4 host integration | Blocked by compatibility test | 26.10 not in supported list |
| webclip frontend | Deferred | Existing services must be preserved |

Agent must replace planned statuses only with evidence from tests or actual machine runs.
