#!/bin/bash
# WSL (root): verify ~/tb138fc/rootfs.img and (re)generate out/rootfs.simg
set -eo pipefail
source /mnt/e/windows_project/tablet_linux/env.sh
IMG=/home/prizmblue/tb138fc/rootfs.img
e2fsck -fn "$IMG"
img2simg "$IMG" "$OUT/rootfs.simg"
ls -l "$OUT/rootfs.simg"
