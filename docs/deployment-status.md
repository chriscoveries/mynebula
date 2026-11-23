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

## Initial CI

The 2026-11-23 commit `5c4e5caa` passed GitHub Actions unit, syntax and compile checks. Boot validation, firmware cases and a live install have not been tested.

## Known issues (2026-11-23)
- **Wi-Fi:** `scripts/render-ventoy-template.py` lists five Wi-Fi interface names (`WIFI_IFACES`). netplan apply fails when a named interface is absent (NETWORK_FAIL in the installer on the Precision 7550). The 7550 was installed with a config naming only its real interfaces (wlo1/eno2). Fix before the stick is used on another machine.
- **Live installer storage probe:** YUMI's `VentoyPart` dm device crashes the curtin storage probe. The early-command `dmsetup remove VentoyPart` is in the templates but not yet re-tested from the stick.
