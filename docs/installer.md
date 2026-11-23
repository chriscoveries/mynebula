# Unattended installer workflow

**Warning:** A remastered ISO adds the `autoinstall` kernel argument. Booting it can automatically erase the disk that matches the config. Make a different, per-node ISO for each host. Never reuse it on another machine.

## Dependencies on the ISO-building machine

Ubuntu/Debian: `sudo apt-get install xorriso python3-venv`; create a venv with `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt`.

Download the official **ubuntu-26.10-live-server-amd64.iso** from https://releases.ubuntu.com/26.10/ and independently check its SHA256 against https://releases.ubuntu.com/26.10/SHA256SUMS.

## 1. Get exact disk identity and public SSH key

On a booted rescue system/old OS, inspect `lsblk -d -o NAME,SIZE,MODEL,SERIAL,TRAN`, `udevadm info` and `scripts/preflight.sh`. Confirm the exact udev ID_SERIAL string. It must uniquely identify the OS SSD. A bad match makes installation fail or destroys an unintended disk.

Prepare two private local files:

- `build/host1/admin.pub`: the intended administrator's existing SSH **public** key.
- `build/host1/password.hash`: a **SHA-512 crypt** console-recovery password hash. Generate with `openssl passwd -6`, then store only the hash in that local file.

Optional: `build/host1/tailscale-auth.key` holding a short-lived, **single-use, tagged** Tailscale auth key. The token will be present in the ISO and may be retained in install/cloud-init records after boot. Keep generated ISOs private; revoke unused credentials and securely dispose of build media. For a safer mode, omit this and join the tailnet after installation.

## 2. Render an exact host-specific config

```bash
.venv/bin/python scripts/render-autoinstall.py \
  --hostname hypervisor-1 \
  --disk-serial 'EXACT_OS_SSD_ID_SERIAL' \
  --ssh-public-key-file build/host1/admin.pub \
  --password-hash-file build/host1/password.hash \
  --output build/host1/autoinstall.yaml
```

Append `--tailscale-auth-key-file build/host1/tailscale-auth.key` for fully unattended Tailscale enrolment. The generated `autoinstall.yaml` is **private** and Git-ignored.

The stock config uses a `direct` ext4 layout on that selected SSD, no swap file, OpenSSH SSH-key auth, local user `hyper`, and first-boot packages for KVM/libvirt, VFIO tools, and RDMA inspection. It leaves VM datastore drives untouched if the disk serial is correct.

## 3. Build the one-USB ISO (destructive)

```bash
bash scripts/build-iso.sh \
  ubuntu-26.10-live-server-amd64.iso \
  build/host1/autoinstall.yaml \
  build/host1/hypervisor-1-AUTO-WIPES.iso \
  --yes-i-understand-disks-will-be-erased
```

Verify the ISO boot path in a disposable QEMU VM with a disposable serial and disk. Test with the same firmware mode as the real host. Write to a USB only after review and physical disk approval. **Never place this ISO on a generic boot server.**

## 4. First boot

Cloud-init installs KVM/libvirt packages and runs `scripts/firstboot-node.sh` (embedded in the ISO), which installs Tailscale from its Ubuntu 26.10 repository. With an embedded one-use key the host can join automatically. Without it, an operator runs `tailscale up` after first boot.

## 5. Handoff

SSH to the new host over Tailscale or the management LAN, execute `scripts/verify-node.sh` from a fresh clone and follow `docs/validation.md`. Install OpenNebula host packages only after the compatibility gate in `docs/opennebula.md`.

## Notes

- This ISO-building path remasters GRUB and preserves recognised boot records using `xorriso -boot_image any replay`. It still requires real BIOS/UEFI boot validation on 26.10 before use.
- Generated images contain a password **hash**, public SSH key, unique disk ID and possibly a sensitive auth key. Do not upload them.
- Ubuntu's installer defaults to asking for confirmation unless `autoinstall` is on the kernel command line. This script deliberately adds it.
- For testing with lower risk, a stock Ubuntu ISO plus separate `CIDATA` NoCloud seed allows an interactive disk-wipe confirmation.

## Running the verifier

Use `sudo bash scripts/verify-node.sh` on the installed host. The verifier uses system libvirt access, which generally requires privileged authorization on Ubuntu 26.10.
