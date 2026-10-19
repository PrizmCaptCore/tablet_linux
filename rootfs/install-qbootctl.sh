#!/bin/sh
# On the tablet (root), or in the rootfs chroot: build linux-msm/qbootctl and mark the current
# A/B slot successful on every boot. Without it abl decrements the slot retry counter on each
# boot and eventually flags boot_a unbootable (it then only shows fastboot).
set -e
pacman -S --noconfirm --needed git meson ninja gcc pkgconf zlib >/dev/null
rm -rf /tmp/qbootctl
git clone -q --depth 1 https://github.com/linux-msm/qbootctl /tmp/qbootctl
cd /tmp/qbootctl
meson setup build --prefix=/usr/local >/dev/null
ninja -C build >/dev/null
install -m 755 build/qbootctl /usr/local/bin/qbootctl
cat > /etc/systemd/system/tb138fc-boot-success.service <<'EOF'
[Unit]
Description=Mark the current A/B boot slot successful (qbootctl)
After=local-fs.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/qbootctl -m

[Install]
WantedBy=multi-user.target
EOF
systemctl enable tb138fc-boot-success.service
rm -rf /tmp/qbootctl
