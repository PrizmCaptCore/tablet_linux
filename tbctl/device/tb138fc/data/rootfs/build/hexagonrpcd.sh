#!/bin/sh
# In the image chroot (tbctl rootfs build --device tb138fc) or on the tablet as root: build
# linux-msm/hexagonrpc with registry write support (hexagonrpcd-patches/) and set up the
# writable sensor registry. hexagonrpcd serves the stock sensor files (hexagonfs, from
# `tbctl firmware hexagonfs`) to the SLPI ("sdsp"); libssc and iio-sensor-proxy from the Arch
# Linux ARM repos then expose the sensors to GNOME. Unit, udev rules and the ld.so path come
# from rootfs/overlay.
#   sh hexagonrpcd.sh [DIR_WITH_PATCHES]      (default: /tmp/hexagonrpcd-patches)
set -e
PATCHES=$(readlink -f "${1:-/tmp/hexagonrpcd-patches}")
REV=598b591ae9da6a6cfe2ca5ea78998019ca6395ea   # the patches' base
ROOT=/usr/share/qcom/sm8250/Lenovo/TB138FC
STATE=/var/lib/hexagonrpcd/persist   # writable /persist/sensors/registry for the SLPI
pacman -S --noconfirm --needed git meson ninja gcc pkgconf json-c libssc iio-sensor-proxy >/dev/null

rm -rf /tmp/hexagonrpc
git init -q /tmp/hexagonrpc
cd /tmp/hexagonrpc
git fetch -q --depth 1 https://github.com/linux-msm/hexagonrpc $REV
git checkout -q FETCH_HEAD
git apply "$PATCHES"/0*.patch
meson setup build --prefix=/usr/local -Dhexagonrpcd_verbose=false >/dev/null
ninja -C build >/dev/null
meson install -C build >/dev/null   # hexagonrpcd links against libhexagonrpc.so
ldconfig
cd / && rm -rf /tmp/hexagonrpc

getent group fastrpc >/dev/null || groupadd -r fastrpc
getent passwd fastrpc >/dev/null || useradd -r -g fastrpc -d / -s /usr/bin/nologin fastrpc

# seed the writable registry from the stock one once; the SLPI keeps it up to date afterwards
if [ ! -d "$STATE/registry" ]; then
	mkdir -p "$STATE"
	cp -a "$ROOT/sensors/registry" "$STATE/registry"
	cp "$ROOT/sensors/sns_reg_version" "$STATE/"
fi
chown -R fastrpc:fastrpc /var/lib/hexagonrpcd
ln -sfn "$STATE" "$ROOT/sensors/persist"
