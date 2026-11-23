#!/usr/bin/env bash
# MyNebula first boot (run by mynebula-firstboot.service until it succeeds once).
# Steps: SSH + libvirt up, Tailscale join (tagged), OpenNebula 7.4 KVM node packages,
# frontend oneadmin public key, scrub the Tailscale key from install records.
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
[[ "$EUID" -eq 0 ]] || { echo 'First boot requires root' >&2; exit 1; }
. /etc/os-release
case "$VERSION_ID" in
  26.04) ONE_UBUNTU=26.04 ;;
  *) echo "Unsupported OS for OpenNebula 7.4 node: $PRETTY_NAME" >&2; exit 1 ;;
esac
CODENAME="${VERSION_CODENAME:?}"
STATE=/var/lib/mynebula
CONF=/etc/mynebula
install -d -m 0755 "$STATE" /etc/apt/keyrings
# Hostname: the installer's late-command sets it, but cloud-init may have reset it from identity.
if [[ "$(hostname)" == nebula-node ]]; then
  NIC=$(for d in /sys/class/net/*; do [[ -e $d/device ]] && basename "$d"; done | sort | head -1)
  H="nebula-$(tr -d ':' < "/sys/class/net/$NIC/address" | tail -c 7)"
  hostnamectl set-hostname "$H"
  sed -i "s/\bnebula-node\b/$H/g" /etc/hosts
fi
echo "MyNebula firstboot start: $(date -u +%FT%TZ) host=$(hostname)"

# Wait for working DNS + HTTPS (the unit already orders after network-online).
for _ in $(seq 1 30); do
  curl -fsS -o /dev/null https://pkgs.tailscale.com/ && break
  sleep 10
done

systemctl enable --now ssh
printf 'vfio\nvfio-pci\n' > /etc/modules-load.d/mynebula-vfio.conf
modprobe vfio || true; modprobe vfio-pci || true

# --- Tailscale --------------------------------------------------------------
if [[ ! -e "$STATE/tailscale-done" ]]; then
  curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/${CODENAME}.noarmor.gpg" \
    -o /usr/share/keyrings/tailscale-archive-keyring.gpg
  curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/${CODENAME}.tailscale-keyring.list" \
    -o /etc/apt/sources.list.d/tailscale.list
  apt-get update -q
  apt-get install -y -q tailscale
  systemctl enable --now tailscaled
  if [[ -s "$CONF/tailscale-auth.key" ]]; then
    TAGS=$(cat "$CONF/tailscale-tags" 2>/dev/null || echo tag:nebula-node)
    if ! tailscale up --auth-key="file:$CONF/tailscale-auth.key" --hostname="$(hostname)" \
         --advertise-tags="$TAGS" --accept-dns=false --ssh=false; then
      # Key not allowed to use the tag: join untagged; the frontend also enrols nebula-* hosts.
      echo "tailscale up with $TAGS failed; retrying untagged" >&2
      tailscale up --auth-key="file:$CONF/tailscale-auth.key" --hostname="$(hostname)" \
        --accept-dns=false --ssh=false
    fi
    touch "$STATE/tailscale-done"
  else
    echo 'No Tailscale key on this node: run "tailscale up" by hand' >&2
    touch "$STATE/tailscale-manual"
  fi
fi

# --- OpenNebula 7.4 KVM node -------------------------------------------------
if [[ ! -e "$STATE/one-node-done" ]]; then
  curl -fsSL https://downloads.opennebula.io/repo/repo2.key | gpg --dearmor --yes -o /etc/apt/keyrings/opennebula.gpg
  echo "deb [signed-by=/etc/apt/keyrings/opennebula.gpg] https://downloads.opennebula.io/repo/7.4/Ubuntu/${ONE_UBUNTU} stable opennebula" \
    > /etc/apt/sources.list.d/opennebula.list
  apt-get update -q
  apt-get install -y -q opennebula-node-kvm
  systemctl restart libvirtd 2>/dev/null || systemctl restart virtqemud 2>/dev/null || true
  touch "$STATE/one-node-done"
fi
if [[ -s "$CONF/frontend-oneadmin.pub" ]]; then
  install -d -o oneadmin -g oneadmin -m 0700 /var/lib/one/.ssh
  touch /var/lib/one/.ssh/authorized_keys
  grep -qxF -f "$CONF/frontend-oneadmin.pub" /var/lib/one/.ssh/authorized_keys \
    || cat "$CONF/frontend-oneadmin.pub" >> /var/lib/one/.ssh/authorized_keys
  chown oneadmin:oneadmin /var/lib/one/.ssh/authorized_keys
  chmod 0600 /var/lib/one/.ssh/authorized_keys
fi

# --- Scrub the Tailscale key from every install record -----------------------
if [[ -e "$STATE/tailscale-done" ]]; then
  shred -u "$CONF/tailscale-auth.key" 2>/dev/null || rm -f "$CONF/tailscale-auth.key"
  grep -rlZ 'tskey-' /var/log/installer /var/lib/cloud /var/log/cloud-init*.log /etc/cloud 2>/dev/null \
    | xargs -0r sed -i -E 's/tskey-[A-Za-z0-9_-]+/tskey-REDACTED/g'
fi

sudo -u oneadmin virsh -c qemu:///system list --all >/dev/null 2>&1 \
  && echo 'oneadmin libvirt access OK' || echo 'WARNING: oneadmin cannot reach qemu:///system' >&2
touch "$STATE/firstboot-complete"
echo "MyNebula firstboot complete: $(date -u +%FT%TZ)"
