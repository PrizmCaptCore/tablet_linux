#!/bin/bash
# Build the initramfs: Alpine minirootfs (busybox) + busybox-extras (telnetd/udhcpd)
# + small static helpers, with initramfs/init as /init.
#   bash initramfs/mkinitramfs.sh
set -eo pipefail
source "$(dirname "$(readlink -f "$0")")/../env.sh"
mkdir -p "$WORK/dl" && cd "$WORK/dl"
REL=https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/aarch64
PKG=https://dl-cdn.alpinelinux.org/alpine/$ALPINE_BRANCH/main/aarch64

MINI=$(curl -s $REL/latest-releases.yaml | grep -m1 -E '^\s+file: alpine-minirootfs-.*-aarch64.tar.gz' | awk '{print $2}')
[ -f "$MINI" ] || curl -sLO "$REL/$MINI"
curl -s $PKG/APKINDEX.tar.gz | tar -xzO APKINDEX > APKINDEX
BBX=$(awk 'BEGIN{RS=""} /\nP:busybox-extras\n/' APKINDEX | grep '^V:' | cut -d: -f2)
[ -f busybox-extras-$BBX.apk ] || curl -sLO "$PKG/busybox-extras-$BBX.apk"

R=$WORK/initramfs
rm -rf "$R" && mkdir -p "$R"
tar -xzf "$MINI" -C "$R"
tar -xzf "busybox-extras-$BBX.apk" -C "$R" --exclude='.*' 2>/dev/null || true
for t in rebootmode devmem; do
  aarch64-linux-gnu-gcc -static -O2 -o "$R/bin/$t" "$REPO/initramfs/src/$t.c"
done
install -m 755 "$REPO/initramfs/init" "$R/init"
(cd "$R" && find . | cpio -o -H newc --quiet | gzip -9) > "$OUT/initramfs.cpio.gz"
ls -l "$OUT/initramfs.cpio.gz"
