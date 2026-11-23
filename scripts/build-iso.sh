#!/usr/bin/env bash
# Patch GRUB and embed autoinstall.yaml without rebuilding the original ISO tree.
set -Eeuo pipefail
usage() {
  cat >&2 <<'EOF'
Usage:
  bash scripts/build-iso.sh ORIGINAL_UBUNTU_26.10_SERVER.iso \
    build/HOST/autoinstall.yaml build/HOST/HOST-AUTO-WIPES.iso \
    --yes-i-understand-disks-will-be-erased

DANGER: A resulting ISO can wipe its configured disk without a prompt.
Test in a disposable VM first. Requires xorriso and Python 3.
EOF
}
if [[ $# -ne 4 || "$4" != "--yes-i-understand-disks-will-be-erased" ]]; then
  usage; exit 2
fi
BASE="$1"; CFG="$2"; OUT="$3"
[[ -f "$BASE" && -f "$CFG" ]] || { echo 'Missing ISO/config' >&2; exit 2; }
[[ ! -e "$OUT" ]] || { echo 'Output exists; refusing overwrite' >&2; exit 2; }
[[ "$OUT" != "$BASE" ]] || { echo 'Output equals input' >&2; exit 2; }
[[ "$OUT" == *AUTO-WIPES.iso ]] || { echo 'Output must end AUTO-WIPES.iso' >&2; exit 2; }
grep -q '^autoinstall:' "$CFG" || { echo 'Missing autoinstall top-level key' >&2; exit 2; }
grep -Eq '^[[:space:]]+serial: ' "$CFG" || { echo 'Missing disk serial selector' >&2; exit 2; }
command -v xorriso >/dev/null || { echo 'Install xorriso' >&2; exit 2; }
command -v python3 >/dev/null || { echo 'Install python3' >&2; exit 2; }
BASE="$(realpath "$BASE")"
CFG="$(realpath "$CFG")"
mkdir -p "$(dirname "$OUT")"
OUT="$(realpath -m "$OUT")"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
umask 077
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
xorriso -osirrox on -indev "$BASE" -extract /boot/grub/grub.cfg "$TMP/grub.cfg"
chmod u+w "$TMP/grub.cfg"
python3 "$SCRIPT_DIR/patch-grub.py" "$TMP/grub.cfg"
echo "Building PRIVATE destructive ISO: $OUT"
xorriso -indev "$BASE" -outdev "$OUT" \
  -map "$TMP/grub.cfg" /boot/grub/grub.cfg \
  -map "$CFG" /autoinstall.yaml \
  -boot_image any replay
sha256sum "$OUT"
echo 'Built ISO; BIOS/UEFI validation still required before bare-metal boot.'
