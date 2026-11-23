# Validation and acceptance checklist

Run tests on a disposable VM before producing media for real hardware. Capture outputs in `build/` only; commit redacted conclusions to `docs/deployment-status.md`.

## Repo checks

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
bash -n scripts/*.sh
```

CI performs these non-destructive checks. They do not prove that the remastered ISO boots.

## Image tests

- Download Ubuntu 26.10 Server ISO, verify checksum.
- Render a test profile with a fake SSH key, crypt hash and disposable disk serial.
- Run the ISO builder. Inspect `/autoinstall.yaml` and `/boot/grub/grub.cfg` with xorriso.
- Boot a QEMU VM, with a **separate disposable disk whose serial exactly matches the test profile**. Observe full installation to the first boot and KVM/libvirt readiness. Use UEFI with OVMF; test legacy BIOS as applicable.
- Confirm a wrong disk serial causes safe failure, and malformed profiles are rejected by renderer.
- Confirm correct guest access and that the built image cannot start modifying another disk during normal testing.

## Per real host read-only checks

```bash
bash scripts/preflight.sh
sudo bash scripts/verify-node.sh
```

After deployment, verify actual kernel via `uname -r` (7.3 family), `timedatectl`, SSH key auth, service status, `virsh -c qemu:///system list --all`, `/dev/kvm` and `tailscale status`. Confirm data disks remain intact. Check logs: `journalctl -u mynebula` if present and `/var/log/cloud-init-output.log` after redacting possible keys.

## Hardware acceptance

- BIOS VT-d enabled and kernel IOMMU groups exist, with no unwanted shared groups for planned GPUs.
- Dedicated management link survives a reboot, if approved. Firmware/console recovery tested.
- NIC link speed and RDMA mode/driver verified on real hardware, without assuming RDMA works solely because packages are installed.
- Optional single GPU can be passed to a disposable VM and returned to the host; only after approved binding.
- Record idle wall-power and CPU package C-state before NIC addition, after boot and after pass-through changes.

## OpenNebula gate

One host successfully registered and `ON` in OpenNebula 7.4, with a guest VM launched, after separate host-package compatibility validation. This is explicitly out of scope for initial OS image completion.

Agent must validate non-root libvirt access separately for the oneadmin service identity, once created. On 26.10, polkit may deny socket access even if the user belongs to a libvirt group.
