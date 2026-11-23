#!/usr/bin/env bash
# Embedded in autoinstall.user-data by render-autoinstall.py.
# Install Tailscale from its signed Ubuntu 26.10 apt repository.
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
if [[ "$EUID" -ne 0 ]]; then
  echo 'First boot requires root' >&2; exit 1
fi
. /etc/os-release
if [[ "$ID" != "ubuntu" || "$VERSION_ID" != "26.10" ]]; then
  echo "Unexpected OS: $PRETTY_NAME" >&2; exit 1
fi
install -d -m 0755 /var/lib/mynebula /usr/share/keyrings /etc/apt/sources.list.d
echo "MyNebula firstboot: $(date -u +%FT%TZ)"
systemctl enable --now ssh
if systemctl cat libvirtd.socket >/dev/null 2>&1; then
  systemctl enable --now libvirtd.socket
elif systemctl cat virtqemud.socket >/dev/null 2>&1; then
  systemctl enable --now virtqemud.socket
else
  echo 'WARNING: libvirt socket missing' >&2
fi
# Prepare VFIO, without binding a specific PCI device.
printf 'vfio\nvfio-pci\n' > /etc/modules-load.d/mynebula-vfio.conf
modprobe vfio || true
modprobe vfio-pci || true
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/stonking.noarmor.gpg \
  -o /usr/share/keyrings/tailscale-archive-keyring.gpg
chmod 0644 /usr/share/keyrings/tailscale-archive-keyring.gpg
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/stonking.tailscale-keyring.list \
  -o /etc/apt/sources.list.d/tailscale.list
apt-get update
apt-get install -y tailscale
systemctl enable --now tailscaled
AUTHFILE=/etc/mynebula/tailscale-auth.key
if [[ -s "$AUTHFILE" ]]; then
  chmod 0600 "$AUTHFILE"
  if tailscale up --auth-key="file:$AUTHFILE" --hostname="$(hostname)" --accept-dns=false; then
    rm -f -- "$AUTHFILE"
    echo 'Tailscale enrollment succeeded'
  else
    echo 'Tailscale enrollment failed; recover via management LAN' >&2
    exit 1
  fi
else
  echo 'Tailscale awaits operator login or separate one-time key'
fi
virsh -c qemu:///system list --all || true
touch /var/lib/mynebula/firstboot-complete
echo 'MyNebula firstboot complete'
