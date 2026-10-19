#!/bin/bash
# Windows (Git Bash): flash out/boot.img to boot_a and out/rootfs.simg to userdata, then boot.
# Gets the tablet into fastboot first if it is running our debug initramfs.
#   bash tools/flash-all.sh
REPO=$(cd "$(dirname "$0")/.." && pwd)
W() { cygpath -w "$1"; }    # Windows paths for fastboot.exe / python.exe
export MSYS_NO_PATHCONV=1   # keep remote paths such as /tmp untouched
FB="$LOCALAPPDATA/Android/platform-tools/fastboot.exe"
for f in boot.img rootfs.simg; do [ -f "$REPO/out/$f" ] || { echo "missing out/$f"; exit 1; }; done

if [ -z "$(timeout 3 "$FB" devices 2>/dev/null)" ]; then
  timeout 20 python "$(W "$REPO/tools/tssh.py")" --root 'systemctl reboot --reboot-argument=bootloader' >/dev/null 2>&1 || \
    timeout 15 python "$(W "$REPO/tools/tsh.py")" 'sync; /bin/rebootmode bootloader' >/dev/null 2>&1 || true
  t=0; until [ -n "$(timeout 3 "$FB" devices 2>/dev/null)" ] || [ $t -ge 120 ]; do sleep 2; t=$((t+2)); done
fi
[ -z "$(timeout 3 "$FB" devices 2>/dev/null)" ] && { echo "no fastboot device"; exit 1; }
sleep 3
set -e
"$FB" flash boot_a "$(W "$REPO/out/boot.img")"
"$FB" flash userdata "$(W "$REPO/out/rootfs.simg")"
"$FB" reboot
