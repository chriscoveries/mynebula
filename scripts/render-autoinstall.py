#!/usr/bin/env python3
"""Create a PRIVATE per-host direct-media Subiquity autoinstall.yaml.

Requires PyYAML. The output may contain a Tailscale key. Never commit it.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import re
import sys
import yaml

FIRSTBOOT = Path(__file__).resolve().parent / "firstboot-node.sh"
PACKAGES = [
    "ca-certificates", "curl", "gnupg", "openssh-server",
    "qemu-system-x86", "qemu-utils", "libvirt-daemon-system",
    "libvirt-clients", "virtinst", "ovmf", "swtpm",
    "pciutils", "usbutils", "ethtool", "iproute2", "bridge-utils",
    "dmidecode", "driverctl", "numactl", "hwloc", "cpu-checker",
    "rdma-core", "ibverbs-utils", "infiniband-diags", "jq", "sysstat",
]


def read_one(path: str) -> str:
    s = Path(path).read_text(encoding="utf-8").strip()
    if not s or "\n" in s or "\r" in s:
        raise ValueError(f"Expected one nonempty line in {path}")
    return s


def make_config(hostname: str, disk_serial: str, public_key: str,
                password_hash: str, tailscale_key: str | None = None) -> dict:
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,62}", hostname) or hostname.endswith("-"):
        raise ValueError("Invalid lowercase hostname")
    # Reject wildcard matching; agent must audit the exact ID_SERIAL.
    if not re.fullmatch(r"[A-Za-z0-9_.:+@-]{4,128}", disk_serial):
        raise ValueError("Use an exact ID_SERIAL without globbing")
    if not re.match(r"^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp\d+)\s+[A-Za-z0-9+/=]+(?:\s|$)", public_key):
        raise ValueError("Expected OpenSSH public key")
    if not password_hash.startswith("$6$"):
        raise ValueError("Expected SHA-512 crypt hash (openssl passwd -6)")
    if tailscale_key is not None and not re.fullmatch(r"tskey-auth-[A-Za-z0-9_-]+", tailscale_key):
        raise ValueError("Invalid Tailscale auth key format")
    files = [{
        "path": "/usr/local/sbin/mynebula-firstboot.sh",
        "permissions": "0755", "owner": "root:root",
        "content": FIRSTBOOT.read_text(encoding="utf-8"),
    }]
    if tailscale_key:
        files.append({
            "path": "/etc/mynebula/tailscale-auth.key",
            "permissions": "0600", "owner": "root:root",
            "content": tailscale_key + "\n",
        })
    return {"autoinstall": {
        "version": 1,
        "locale": "en_AU.UTF-8",
        "timezone": "Australia/Sydney",
        "identity": {
            "hostname": hostname, "username": "hyper", "password": password_hash,
        },
        "ssh": {
            "install-server": True, "allow-pw": False, "authorized-keys": [public_key],
        },
        "storage": {
            "layout": {"name": "direct", "match": {"serial": disk_serial}},
            "swap": {"size": 0},
        },
        "updates": "security",
        "user-data": {
            "package_update": True,
            "packages": PACKAGES,
            "write_files": files,
            "runcmd": [["/usr/local/sbin/mynebula-firstboot.sh"]],
        },
    }}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hostname", required=True)
    p.add_argument("--disk-serial", required=True, help="exact ID_SERIAL; erases the matching disk")
    p.add_argument("--ssh-public-key-file", required=True)
    p.add_argument("--password-hash-file", required=True)
    p.add_argument("--tailscale-auth-key-file", help="optional one-use key embedded in ISO")
    p.add_argument("--output", required=True, help="private build/HOST/autoinstall.yaml")
    a = p.parse_args()
    try:
        token = None
        if a.tailscale_auth_key_file:
            keypath = Path(a.tailscale_auth_key_file)
            if keypath.stat().st_mode & 0o077:
                raise ValueError("Auth key file permissions must be 0600")
            token = read_one(str(keypath))
        obj = make_config(
            a.hostname, a.disk_serial, read_one(a.ssh_public_key_file),
            read_one(a.password_hash_file), token,
        )
        output = Path(a.output)
        if output.name != "autoinstall.yaml":
            raise ValueError("Output filename must be autoinstall.yaml")
        os.umask(0o077)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as handle:
            yaml.safe_dump(obj, handle, sort_keys=False, allow_unicode=True)
        print(f"Private config created: {output}; target ID_SERIAL={a.disk_serial}")
        if token:
            print("WARNING: ISO/cloud-init records may retain a Tailscale auth key")
        return 0
    except (ValueError, OSError, yaml.YAMLError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
