#!/usr/bin/env python3
"""Frontend side of MyNebula zero-touch enrolment (runs on webclip as root, via timer).

Every online tailnet peer tagged tag:nebula-node that finished first boot becomes an OpenNebula KVM host.
Idempotent: hosts already known to oned are skipped. Never removes or changes existing hosts.
"""
import json
import subprocess
import sys

TAG = "tag:nebula-node"


def run(cmd, user=None, check=True):
    if user:
        cmd = ["runuser", "-u", user, "--"] + cmd
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=check)


def main() -> int:
    status = json.loads(run(["tailscale", "status", "--json"]).stdout)
    pool = json.loads(run(["onehost", "list", "--json"], user="oneadmin").stdout).get("HOST_POOL") or {}
    hosts = pool.get("HOST") or []
    if isinstance(hosts, dict):  # oned returns a single host as an object
        hosts = [hosts]
    known = {h.get("NAME") for h in hosts}
    for peer in status.get("Peer", {}).values():
        tagged = TAG in (peer.get("Tags") or [])
        named = peer.get("HostName", "").startswith("nebula-") and peer.get("OS") == "linux"
        if not (tagged or named) or not peer.get("Online"):
            continue
        name = peer["DNSName"].rstrip(".")
        if name in known:
            continue
        # The node finishes first boot (oneadmin key installed) before oneadmin SSH works.
        probe = run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", name,
                     "test -e /var/lib/mynebula/firstboot-complete"], user="oneadmin", check=False)
        if probe.returncode != 0:
            print(f"waiting: {name} (oneadmin ssh or first boot not ready)")
            continue
        out = run(["onehost", "create", name, "-i", "kvm", "-v", "kvm"], user="oneadmin", check=False)
        print(f"enrol {name}: rc={out.returncode} {out.stdout.strip()} {out.stderr.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
