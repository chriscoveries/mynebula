# Safety and security policy

## Most important: physical disk destruction

An `autoinstall` kernel argument removes Subiquity's confirmation prompt. The generated ISO will wipe and repartition a disk matched by `storage.layout.match.serial`. Confirm the exact serial against a hardware inventory and the image content immediately before boot. Disconnect unrelated storage during initial validation if practical. No automated agent may run the image on real disks without explicit user approval.

## Credential handling

- Git: public docs and generic scripts only. Never commit a password, private key, Tailscale auth key, full rendered ISO/config or backups that contain them.
- Rendered `autoinstall.yaml` embeds a SHA-512 crypt password hash and public SSH key. Treat it as private due to host-specific metadata.
- Optional Tailscale auth key also becomes part of the ISO and may remain in installer/cloud-init records even after the firstboot script deletes its runtime copy. Use only a short-lived, one-use, appropriately tagged key. Revoke it after use. Encrypt or securely dispose of the ISO/build drive.
- Tailscale direct join after boot is the recommended option if embedded-token exposure is unacceptable.
- Restrict SSH to keys. Keep emergency console access and a local recovery password.
- Keep a known working management network and out-of-band path for NIC bridge, firewall, firmware and VFIO work.
- Audit cloud-init logs for accidental credentials before collecting reports; avoid pasting unredacted outputs.

## Dependency and update policy

Official Ubuntu ISO with checksum verification, normal signed Ubuntu repositories and official Tailscale signed repository. Any unsupported OpenNebula host packages, external DKMS drivers or firmware changes require separate testing and explicit approval.

Ubuntu 26.10's short support window requires an upgrade plan by July 2027. Do not allow unattended OS release upgrades on production hypervisor nodes.
