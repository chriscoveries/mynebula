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
    "thermald", "fwupd",
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
    "sed -i \"s/\\bnebula-node\\b/$H/g\" /target/etc/hosts || true"
)
PLACEHOLDER = "nebula-node"
WIFI_IFACES = ["wlp0s20f3", "wlp2s0", "wlp3s0", "wlo1", "wlan0"]
# IOMMU on (GPU passthrough later), console blanks after 2 min (laptop screen/heat).
GRUB_CMD = (
    "sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT=\"/&intel_iommu=on iommu=pt consoleblank=120 cfg80211.ieee80211_regdom=AU /' /target/etc/default/grub && "
    "curtin in-target --target=/target -- update-grub || true"
)
# A laptop's battery is a free UPS: shut down cleanly before it runs flat.
BATTERY_GUARD = """#!/bin/sh
# mynebula: power off cleanly when on battery and below 10%.
for b in /sys/class/power_supply/BAT*; do
  [ -r "$b/status" ] || continue
  if [ "$(cat $b/status)" = Discharging ] && [ "$(cat $b/capacity)" -le 10 ]; then
    logger -t mynebula-battery "battery $(cat $b/capacity)% and discharging: powering off"
    systemctl poweroff
  fi
done
"""
BATTERY_SERVICE = """[Unit]
Description=MyNebula battery guard (power off below 10% on battery)
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/mynebula-battery-guard
"""
BATTERY_TIMER = """[Unit]
Description=MyNebula battery guard, every minute
[Timer]
OnBootSec=2min
OnUnitActiveSec=1min
[Install]
WantedBy=timers.target
"""
# Boot-time power tuning for a laptop hypervisor. Each step is skipped (and logged) if the hardware lacks it.
POWER_TUNE = """#!/bin/sh
# mynebula: battery charge 75-80%, Wi-Fi power save off, Bluetooth off, balanced platform profile.
log() { logger -t mynebula-power "$*"; echo "$*"; }
for b in /sys/class/power_supply/BAT*; do
  [ -d "$b" ] || continue
  if [ -w "$b/charge_control_end_threshold" ]; then
    # Write end first: some firmware rejects a start above the current end.
    echo 80 > "$b/charge_control_end_threshold" 2>/dev/null
    [ -w "$b/charge_control_start_threshold" ] && echo 75 > "$b/charge_control_start_threshold" 2>/dev/null
    log "$(basename $b): charge limit start=$(cat $b/charge_control_start_threshold 2>/dev/null) end=$(cat $b/charge_control_end_threshold)"
  else
    log "$(basename $b): no kernel charge limit; set it in the BIOS (Battery Charge Configuration: Custom 75/80)"
  fi
done
for w in /sys/class/net/wl*; do
  [ -e "$w" ] || continue
  iw dev "$(basename $w)" set power_save off 2>/dev/null && log "$(basename $w): Wi-Fi power save off"
done
rfkill block bluetooth 2>/dev/null && log "bluetooth blocked"
if [ -w /sys/firmware/acpi/platform_profile ] && grep -qw balanced /sys/firmware/acpi/platform_profile_choices 2>/dev/null; then
  echo balanced > /sys/firmware/acpi/platform_profile && log "platform profile balanced"
fi
exit 0
"""
POWER_SERVICE = """[Unit]
Description=MyNebula laptop power tuning (charge limit, Wi-Fi power save, Bluetooth)
After=network-pre.target
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/mynebula-power-tune
[Install]
WantedBy=multi-user.target
"""
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
                wifi: tuple[str, str] | list[tuple[str, str]] | None = None) -> dict:
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
        {"path": "/usr/local/sbin/mynebula-battery-guard", "permissions": "0755",
         "owner": "root:root", "content": BATTERY_GUARD},
        {"path": "/etc/systemd/system/mynebula-battery-guard.service", "permissions": "0644",
         "owner": "root:root", "content": BATTERY_SERVICE},
        {"path": "/etc/systemd/system/mynebula-battery-guard.timer", "permissions": "0644",
         "owner": "root:root", "content": BATTERY_TIMER},
        {"path": "/usr/local/sbin/mynebula-power-tune", "permissions": "0755",
         "owner": "root:root", "content": POWER_TUNE},
        {"path": "/etc/systemd/system/mynebula-power-tune.service", "permissions": "0644",
         "owner": "root:root", "content": POWER_SERVICE},
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
        # YUMI/Ventoy maps the whole stick partition as dm "VentoyPart"; curtin's probe crashes on it
        # (ValueError: Invalid dep_id (disk-dm-1)). Early-commands run before block probing.
        "early-commands": ["dmsetup remove VentoyPart || true"],
        "late-commands": [HOSTNAME_CMD, GRUB_CMD],
        "user-data": {
            "package_update": True,
            "packages": PACKAGES,
            "write_files": files,
            "runcmd": [["systemctl", "mask", "sleep.target", "suspend.target", "hibernate.target", "hybrid-sleep.target"],
                       ["systemctl", "daemon-reload"],
                       ["systemctl", "enable", "--now", "mynebula-battery-guard.timer"],
                       ["systemctl", "enable", "--now", "mynebula-power-tune.service"],
                       ["systemctl", "enable", "--now", "--no-block", "mynebula-firstboot.service"]],
        },
    }
    if wifi:
        networks = [wifi] if isinstance(wifi, tuple) else list(wifi)
        for ssid, psk in networks:
            if not (1 <= len(ssid.encode()) <= 32) or not (8 <= len(psk) <= 63):
                raise ValueError("Wi-Fi SSID must be 1-32 bytes and the passphrase 8-63 characters")
        aps = {ssid: {"password": psk} for ssid, psk in networks}
        # Wired preferred when both are up (lower metric); Wi-Fi is used when no cable.
        auto["network"] = {"version": 2,
            "ethernets": {"wired": {"match": {"name": "en*"}, "dhcp4": True, "optional": True,
                                    "dhcp4-overrides": {"route-metric": 100}}},
            # networkd can't match Wi-Fi by pattern: name the usual interfaces explicitly
            # (wlp0s20f3 = Intel CNVi AX201/AX211 on Dell Precision 75x0; the others are fallbacks).
            "wifis": {name: {"dhcp4": True, "optional": True,
                             "dhcp4-overrides": {"route-metric": 600},
                             "access-points": aps}
                      for name in WIFI_IFACES}}
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
            lines = [l.rstrip("\r") for l in Path(a.wifi_file).read_text(encoding="utf-8").splitlines() if l.strip()]
            if len(lines) < 2 or len(lines) % 2:
                raise ValueError("Wi-Fi file: pairs of lines, SSID then passphrase")
            wifi = [(lines[i], lines[i + 1]) for i in range(0, len(lines), 2)]
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
