#!/usr/bin/env python3
"""Render a Ventoy auto_install template (cloud-init autoinstall) for Ubuntu 26.04 nodes.

generic mode : the OS disk is chosen ON SCREEN (interactive storage); everything else is automatic.
serial mode  : --disk-serial pins the exact OS disk; fully unattended (per-node template).

The output may contain a Tailscale auth key. It is PRIVATE: never commit it.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import re
import sys
import yaml

HERE = Path(__file__).resolve().parent
FIRSTBOOT = HERE / "firstboot-node.sh"
PACKAGES = [
    "ca-certificates", "curl", "gnupg", "openssh-server",
    "qemu-system-x86", "qemu-utils", "libvirt-daemon-system",
    "libvirt-clients", "virtinst", "ovmf", "swtpm",
    "pciutils", "usbutils", "ethtool", "iproute2", "bridge-utils",
    "dmidecode", "driverctl", "numactl", "hwloc", "cpu-checker",
    "rdma-core", "ibverbs-utils", "infiniband-diags", "jq", "sysstat",
]
SERVICE = """[Unit]
Description=MyNebula first boot (Tailscale + OpenNebula node)
Wants=network-online.target
After=network-online.target cloud-final.service
ConditionPathExists=!/var/lib/mynebula/firstboot-complete
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/mynebula-firstboot.sh
Restart=on-failure
RestartSec=60
StandardOutput=append:/var/log/mynebula-firstboot.log
StandardError=append:/var/log/mynebula-firstboot.log
[Install]
WantedBy=multi-user.target
"""
# Hostname = nebula-<last 6 hex of the first physical NIC MAC>; no prompt, unique per machine.
HOSTNAME_CMD = (
    "N=$(for d in /sys/class/net/*; do [ -e $d/device ] && basename $d; done | sort | head -1); "
    "S=$(tr -d ':' < /sys/class/net/$N/address | tail -c 7); H=nebula-$S; "
    "echo $H > /target/etc/hostname; "
    "sed -i \"s/\\bnebula-node\\b/$H/g\" /target/etc/hosts"
)
PLACEHOLDER = "nebula-node"
# Laptops and desktops as hypervisors: never suspend, ignore the lid.
LOGIND = """[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
HandleSuspendKey=ignore
HandleHibernateKey=ignore
IdleAction=ignore
"""


def read_one(path: str) -> str:
    s = Path(path).read_text(encoding="utf-8").strip()
    if not s or "\n" in s or "\r" in s:
        raise ValueError(f"Expected one nonempty line in {path}")
    return s


def read_keys(path: str) -> list[str]:
    keys = [k.strip() for k in Path(path).read_text(encoding="utf-8").splitlines() if k.strip()]
    for k in keys:
        if not re.match(r"^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp\d+|sk-ssh-ed25519@openssh.com)\s+[A-Za-z0-9+/=]+(\s|$)", k):
            raise ValueError(f"Not an OpenSSH public key: {k[:30]}...")
    if not keys:
        raise ValueError("No SSH public keys")
    return keys


def make_config(public_keys: list[str], password_hash: str, disk_serial: str | None = None,
                tailscale_key: str | None = None, tailscale_tags: str = "tag:nebula-node",
                frontend_pubkey: str | None = None, timezone: str = "Australia/Sydney",
                wifi: tuple[str, str] | None = None) -> dict:
    if not password_hash.startswith("$6$"):
        raise ValueError("Expected SHA-512 crypt hash (openssl passwd -6)")
    if disk_serial is not None and not re.fullmatch(r"[A-Za-z0-9_.:+@-]{4,128}", disk_serial):
        raise ValueError("Use an exact ID_SERIAL without globbing")
    if tailscale_key is not None and not re.fullmatch(r"tskey-auth-[A-Za-z0-9_-]+", tailscale_key):
        raise ValueError("Invalid Tailscale auth key format")
    if not re.fullmatch(r"tag:[a-z0-9-]+(,tag:[a-z0-9-]+)*", tailscale_tags):
        raise ValueError("Tags must look like tag:name[,tag:name]")
    if frontend_pubkey is not None and not frontend_pubkey.startswith(("ssh-ed25519 ", "ssh-rsa ", "ecdsa-")):
        raise ValueError("Frontend oneadmin key must be an OpenSSH public key")

    files = [
        {"path": "/usr/local/sbin/mynebula-firstboot.sh", "permissions": "0755",
         "owner": "root:root", "content": FIRSTBOOT.read_text(encoding="utf-8")},
        {"path": "/etc/systemd/system/mynebula-firstboot.service", "permissions": "0644",
         "owner": "root:root", "content": SERVICE},
        {"path": "/etc/systemd/logind.conf.d/mynebula-no-sleep.conf", "permissions": "0644",
         "owner": "root:root", "content": LOGIND},
        {"path": "/etc/mynebula/tailscale-tags", "permissions": "0644",
         "owner": "root:root", "content": tailscale_tags + "\n"},
    ]
    if tailscale_key:
        files.append({"path": "/etc/mynebula/tailscale-auth.key", "permissions": "0600",
                      "owner": "root:root", "content": tailscale_key + "\n"})
    if frontend_pubkey:
        files.append({"path": "/etc/mynebula/frontend-oneadmin.pub", "permissions": "0644",
                      "owner": "root:root", "content": frontend_pubkey + "\n"})

    auto: dict = {
        "version": 1,
        "locale": "en_AU.UTF-8",
        "keyboard": {"layout": "us"},
        "timezone": timezone,
        "identity": {"hostname": PLACEHOLDER, "username": "hyper", "password": password_hash},
        "ssh": {"install-server": True, "allow-pw": False, "authorized-keys": public_keys},
        "updates": "security",
        "late-commands": [HOSTNAME_CMD],
        "user-data": {
            "package_update": True,
            "packages": PACKAGES,
            "write_files": files,
            "runcmd": [["systemctl", "mask", "sleep.target", "suspend.target", "hibernate.target", "hybrid-sleep.target"],
                       ["systemctl", "daemon-reload"],
                       ["systemctl", "enable", "--now", "--no-block", "mynebula-firstboot.service"]],
        },
    }
    if wifi:
        ssid, psk = wifi
        if not (1 <= len(ssid.encode()) <= 32) or not (8 <= len(psk) <= 63):
            raise ValueError("Wi-Fi SSID must be 1-32 bytes and the passphrase 8-63 characters")
        # Wired preferred when both are up (lower metric); Wi-Fi is used when no cable.
        auto["network"] = {"version": 2,
            "ethernets": {"wired": {"match": {"name": "en*"}, "dhcp4": True, "optional": True,
                                    "dhcp4-overrides": {"route-metric": 100}}},
            "wifis": {"wifi": {"match": {"name": "wl*"}, "dhcp4": True, "optional": True,
                               "dhcp4-overrides": {"route-metric": 600},
                               "access-points": {ssid: {"password": psk}}}}}
        # Installed by the installer itself, so Wi-Fi works on first boot without a cable.
        auto["packages"] = ["wpasupplicant", "linux-firmware", "iw", "wireless-regdb"]
    if disk_serial:
        auto["storage"] = {"layout": {"name": "direct", "match": {"serial": disk_serial}}, "swap": {"size": 0}}
    else:
        # The operator must pick the OS disk on screen. No size/type heuristics.
        auto["interactive-sections"] = ["storage"]
        auto["storage"] = {"layout": {"name": "direct"}, "swap": {"size": 0}}
    return {"autoinstall": auto}


def render(obj: dict) -> str:
    return "#cloud-config\n" + yaml.safe_dump(obj, sort_keys=False, allow_unicode=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ssh-keys-file", required=True, help="one OpenSSH public key per line")
    p.add_argument("--password-hash-file", required=True)
    p.add_argument("--disk-serial", help="exact ID_SERIAL: makes the template fully unattended and ERASES that disk")
    p.add_argument("--tailscale-auth-key-file")
    p.add_argument("--tailscale-tags", default="tag:nebula-node")
    p.add_argument("--frontend-oneadmin-pub")
    p.add_argument("--wifi-file", help="0600 file: line 1 SSID, line 2 passphrase")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    try:
        token = None
        if a.tailscale_auth_key_file:
            if Path(a.tailscale_auth_key_file).stat().st_mode & 0o077:
                raise ValueError("Auth key file permissions must be 0600")
            token = read_one(a.tailscale_auth_key_file)
        wifi = None
        if a.wifi_file:
            if Path(a.wifi_file).stat().st_mode & 0o077:
                raise ValueError("Wi-Fi file permissions must be 0600")
            lines = Path(a.wifi_file).read_text(encoding="utf-8").splitlines()
            if len(lines) < 2:
                raise ValueError("Wi-Fi file needs SSID on line 1 and passphrase on line 2")
            wifi = (lines[0].rstrip("\r"), lines[1].rstrip("\r"))
        obj = make_config(read_keys(a.ssh_keys_file), read_one(a.password_hash_file), a.disk_serial,
                          token, a.tailscale_tags,
                          read_one(a.frontend_oneadmin_pub) if a.frontend_oneadmin_pub else None,
                          wifi=wifi)
        os.umask(0o077)
        out = Path(a.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("x", encoding="utf-8") as handle:
            handle.write(render(obj))
        mode = f"UNATTENDED, erases ID_SERIAL={a.disk_serial}" if a.disk_serial else "operator picks the OS disk on screen"
        print(f"Private template written: {out} ({mode})")
        return 0
    except (ValueError, OSError, yaml.YAMLError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
