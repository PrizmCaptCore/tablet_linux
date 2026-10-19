#!/bin/bash
# Windows (Git Bash): flash out/boot.img to boot_a and boot it.
# If the tablet is running our Linux, it is first rebooted into fastboot over the USB network.
#   bash tools/deploy.sh
REPO=$(cd "$(dirname "$0")/.." && pwd)
W() { cygpath -w "$1"; }    # Windows paths for fastboot.exe / python.exe
export MSYS_NO_PATHCONV=1   # keep remote paths such as /tmp untouched
FB="$LOCALAPPDATA/Android/platform-tools/fastboot.exe"
IMG="$REPO/out/boot.img"
[ -f "$IMG" ] || { echo "missing $IMG (run kernel/mkboot.sh in WSL)"; exit 1; }

if [ -z "$(timeout 3 "$FB" devices 2>/dev/null)" ]; then
  # Arch over ssh, or the debug initramfs over telnet
  timeout 20 python "$(W "$REPO/tools/tssh.py")" --root 'systemctl reboot --reboot-argument=bootloader' >/dev/null 2>&1 || \
    timeout 15 python "$(W "$REPO/tools/tsh.py")" 'sync; /bin/rebootmode bootloader' >/dev/null 2>&1 || true
  t=0; until [ -n "$(timeout 3 "$FB" devices 2>/dev/null)" ] || [ $t -ge 120 ]; do sleep 2; t=$((t+2)); done
fi
[ -z "$(timeout 3 "$FB" devices 2>/dev/null)" ] && { echo "no fastboot device"; exit 1; }
sleep 3
"$FB" flash boot_a "$(W "$IMG")" 2>&1 | tail -1
"$FB" reboot 2>&1 | tail -1
t=0; until ping -n 1 -w 1000 172.16.42.1 >/dev/null 2>&1 || [ $t -ge 90 ]; do sleep 2; t=$((t+2)); done
ping -n 1 -w 1000 172.16.42.1 >/dev/null 2>&1 && echo "tablet up after ~${t}s" || echo "no network after 90s"
