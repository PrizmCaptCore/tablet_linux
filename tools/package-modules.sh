#!/bin/bash
# WSL: install the built kernel modules into a tarball ($OUT/modules-<kver>.tar.gz) for pushing
# to a running tablet (tools/tput.py + tar -C /), instead of rebuilding the whole rootfs.
set -eo pipefail
source "$(dirname "$(readlink -f "$0")")/../env.sh"
KVER=$(make -s -C "$KERNEL" kernelrelease)
T=$WORK/modstage && rm -rf "$T" && mkdir -p "$T"
make -s -C "$KERNEL" INSTALL_MOD_PATH="$T/usr" INSTALL_MOD_STRIP=1 modules_install
rm -f "$T/usr/lib/modules/$KVER/build"
tar -C "$T" --owner=0 --group=0 -czf "$OUT/modules-$KVER.tar.gz" usr
ls -l "$OUT/modules-$KVER.tar.gz"
