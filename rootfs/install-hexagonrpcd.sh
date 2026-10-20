#!/bin/sh
# On the tablet (root), or in the rootfs chroot: build linux-msm/hexagonrpc with registry write
# support (hexagonrpcd-patches/) and serve the stock sensor files (hexagonfs, from
# tbctl firmware hexagonfs) to the SLPI ("sdsp").
# libssc and iio-sensor-proxy from the Arch Linux ARM repos then expose the sensors to GNOME.
#   sh install-hexagonrpcd.sh DIR_WITH_PATCHES
set -e
PATCHES=$(readlink -f "${1:-/tmp/hexagonrpcd-patches}")
COMMIT=598b591ae9da6a6cfe2ca5ea78998019ca6395ea   # the patches' base
ROOT=/usr/share/qcom/sm8250/Lenovo/TB138FC
STATE=/var/lib/hexagonrpcd/persist   # writable /persist/sensors/registry for the SLPI
pacman -S --noconfirm --needed git meson ninja gcc pkgconf json-c libssc iio-sensor-proxy >/dev/null

rm -rf /tmp/hexagonrpc
git clone -q https://github.com/linux-msm/hexagonrpc /tmp/hexagonrpc
cd /tmp/hexagonrpc
git checkout -q $COMMIT
git apply "$PATCHES"/0*.patch
meson setup build --prefix=/usr/local -Dhexagonrpcd_verbose=false >/dev/null
ninja -C build >/dev/null
meson install -C build >/dev/null   # hexagonrpcd links against libhexagonrpc.so
echo /usr/local/lib > /etc/ld.so.conf.d/usr-local.conf
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
cat > /etc/udev/rules.d/80-fastrpc.rules <<'EOF'
KERNEL=="fastrpc-*", GROUP="fastrpc", MODE="0660"
# fastrpc is a module that can show up after multi-user.target starts its services
KERNEL=="fastrpc-sdsp", TAG+="systemd", ENV{SYSTEMD_WANTS}+="hexagonrpcd-sdsp.service"
EOF
# upstream only enables SSC light and compass; the accelerometer needs a per-device mount matrix
# (the ICM4x6xx X/Y axes are swapped relative to the landscape panel; firmware reports none)
cat > /etc/udev/rules.d/79-tb138fc-sensors.rules <<'EOF'
SUBSYSTEM=="misc", KERNEL=="fastrpc-sdsp", ENV{IIO_SENSOR_PROXY_TYPE}+="ssc-accel", ENV{ACCEL_MOUNT_MATRIX}="0, 1, 0; -1, 0, 0; 0, 0, 1"
EOF
# iio-sensor-proxy segfaults when the SLPI restarts underneath it (e.g. after an SLPI crash)
mkdir -p /etc/systemd/system/iio-sensor-proxy.service.d
printf '[Service]
Restart=on-failure
RestartSec=3
' > /etc/systemd/system/iio-sensor-proxy.service.d/restart.conf

cat > /etc/systemd/system/hexagonrpcd-sdsp.service <<EOF
[Unit]
Description=Server for FastRPC remote procedure calls from the Qualcomm SLPI (sensors)
ConditionPathExists=/dev/fastrpc-sdsp
Before=iio-sensor-proxy.service
BindsTo=dev-fastrpc\x2dsdsp.device
After=dev-fastrpc\x2dsdsp.device

[Service]
ExecStart=/usr/local/bin/hexagonrpcd -f /dev/fastrpc-sdsp -d sdsp -s -R $ROOT
Restart=always
RestartSec=3
User=fastrpc
Group=fastrpc

[Install]
WantedBy=multi-user.target
EOF
systemctl enable hexagonrpcd-sdsp.service
