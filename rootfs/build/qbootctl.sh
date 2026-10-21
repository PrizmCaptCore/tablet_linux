#!/bin/sh
# In the image chroot (tbctl rootfs build --device tb138fc) or on the tablet as root: build
# linux-msm/qbootctl into /usr/local/bin. tb138fc-boot-success.service (rootfs/overlay) runs
# `qbootctl -m` on every boot: without it abl decrements the slot retry counter on each boot
# and eventually flags boot_a unbootable (it then only shows fastboot).
set -e
REV=39a6e6daaf029fb0a083777679a15ea2c18f72de
pacman -S --noconfirm --needed git meson ninja gcc pkgconf zlib >/dev/null
rm -rf /tmp/qbootctl
git init -q /tmp/qbootctl
cd /tmp/qbootctl
git fetch -q --depth 1 https://github.com/linux-msm/qbootctl $REV
git checkout -q FETCH_HEAD
meson setup build --prefix=/usr/local >/dev/null
ninja -C build >/dev/null
install -m 755 build/qbootctl /usr/local/bin/qbootctl
cd / && rm -rf /tmp/qbootctl
