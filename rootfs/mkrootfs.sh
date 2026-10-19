#!/bin/bash
# Build the Arch Linux ARM + GNOME root filesystem for the TB138FC (run as root in WSL):
#   sudo bash rootfs/mkrootfs.sh
# Needs the kernel built first (kernel/buildkernel.sh) for modules_install.
# Output: $OUT/rootfs.simg (Android sparse image, flashed to the userdata partition).
set -eo pipefail
# Run in a private mount namespace: under WSL, systemd services copy our loop/bind mounts
# into their own namespaces, which keeps the image mounted after we unmount it.
if [ -z "$TB_UNSHARED" ]; then
  exec env TB_UNSHARED=1 unshare -m --propagation private bash "$(readlink -f "$0")" "$@"
fi
source "$(dirname "$(readlink -f "$0")")/../env.sh"
WORK=/home/prizmblue/tb138fc KERNEL=/home/prizmblue/tb138fc/linux   # env.sh uses $HOME, which is /root under sudo
IMG=$WORK/rootfs.img
MNT=$WORK/rootfs-mnt
TARBALL=$WORK/dl/ArchLinuxARM-aarch64-latest.tar.gz
KVER=$(make -s -C "$KERNEL" kernelrelease)

cleanup() {
  # pacman-key leaves gpg-agent/keyboxd running inside the chroot
  for p in /proc/[0-9]*; do
    case "$(readlink "$p/root" 2>/dev/null)" in "$MNT"*) kill -9 "${p#/proc/}" 2>/dev/null || true;; esac
  done
  for d in dev/pts dev sys proc; do umount -l "$MNT/$d" 2>/dev/null || true; done
  umount -l "$MNT" 2>/dev/null || true
}
trap cleanup EXIT

mkdir -p "$WORK/dl"
[ -f "$TARBALL" ] || curl -L --retry 5 -o "$TARBALL" http://os.archlinuxarm.org/os/ArchLinuxARM-aarch64-latest.tar.gz

cleanup
rm -f "$IMG"
truncate -s 16G "$IMG"
mkfs.ext4 -q -L tb138fc-root "$IMG"
mkdir -p "$MNT"
mount -o loop "$IMG" "$MNT"
bsdtar -xpf "$TARBALL" -C "$MNT"

# chroot plumbing (qemu-aarch64 binfmt has the F flag, so no interpreter copy is needed)
for d in proc sys dev dev/pts; do mount --bind "/$d" "$MNT/$d"; done
rm -f "$MNT/etc/resolv.conf"; cp /etc/resolv.conf "$MNT/etc/resolv.conf"
# Under qemu-user/WSL: no Landlock for pacman's sandbox, and the disk-space check fails.
sed -i 's/^#\?DisableSandbox.*//; s/^CheckSpace/#CheckSpace/; /^\[options\]/a DisableSandbox' "$MNT/etc/pacman.conf"

chroot "$MNT" /bin/bash -eo pipefail <<'CHROOT'
pacman-key --init
pacman-key --populate archlinuxarm
# we ship our own kernel; drop the generic one and its initramfs hooks
pacman -Rns --noconfirm linux-aarch64 || true
pacman -Syu --noconfirm
# gnome-books and gnome-boxes have unresolvable deps (libsoup) on Arch Linux ARM, and
# --ignore does not apply to group selection, so install the group members explicitly.
GNOME_PKGS=$(pacman -Sgq gnome | grep -v -x -e gnome-books -e gnome-boxes)
pacman -S --noconfirm --needed $GNOME_PKGS gdm networkmanager openssh sudo noto-fonts noto-fonts-cjk noto-fonts-emoji \
    pipewire-jack alsa-utils iio-sensor-proxy mesa linux-firmware-qcom bluez bluez-utils e2fsprogs usbutils i2c-tools vim
systemctl enable gdm NetworkManager sshd systemd-networkd bluetooth
echo tb138fc > /etc/hostname
echo 'LANG=ko_KR.UTF-8' > /etc/locale.conf
sed -i 's/^#\(ko_KR.UTF-8\)/\1/; s/^#\(en_US.UTF-8\)/\1/' /etc/locale.gen
locale-gen
ln -sf /usr/share/zoneinfo/Asia/Seoul /etc/localtime
echo '%wheel ALL=(ALL:ALL) ALL' > /etc/sudoers.d/wheel
usermod -aG wheel alarm
CHROOT

# mark the A/B slot successful on every boot (otherwise abl flags boot_a unbootable)
cp "$REPO/rootfs/install-qbootctl.sh" "$MNT/tmp/"
chroot "$MNT" /bin/sh /tmp/install-qbootctl.sh

# SLPI sensors: stock sensor files + patched hexagonrpcd (tools/build-hexagonfs.sh)
if [ -f "$OUT/hexagonfs-tb138fc.tar.gz" ]; then
  tar -xzf "$OUT/hexagonfs-tb138fc.tar.gz" -C "$MNT"
  rm -rf "$MNT/tmp/hexagonrpcd-patches"; cp -r "$REPO/rootfs/hexagonrpcd-patches" "$MNT/tmp/"
  cp "$REPO/rootfs/install-hexagonrpcd.sh" "$MNT/tmp/"
  chroot "$MNT" /bin/sh /tmp/install-hexagonrpcd.sh /tmp/hexagonrpcd-patches
else
  echo "WARNING: $OUT/hexagonfs-tb138fc.tar.gz missing - no sensors" >&2
fi

# Speakers: UCM for the 4x CS35L43 card + factory calibration from persist
cp -r "$REPO/rootfs/ucm2/Lenovo" "$MNT/usr/share/alsa/ucm2/"
mkdir -p "$MNT/usr/share/alsa/ucm2/conf.d/sm8250"
ln -sfn ../../Lenovo/TB138FC/TB138FC.conf "$MNT/usr/share/alsa/ucm2/conf.d/sm8250/Lenovo-TB138FC.conf"
install -m 755 "$REPO/rootfs/tb138fc-spk-cal" "$MNT/usr/local/bin/tb138fc-spk-cal"
install -m 644 "$REPO/rootfs/tb138fc-spk-cal.service" "$MNT/etc/systemd/system/"
ln -sf /etc/systemd/system/tb138fc-spk-cal.service "$MNT/etc/systemd/system/multi-user.target.wants/"

# Bluetooth/Wi-Fi addresses from fpinfo (QCA6390 BT stays unconfigured without a BD address)
install -m 755 "$REPO/rootfs/tb138fc-macs" "$MNT/usr/local/bin/tb138fc-macs"
install -m 644 "$REPO/rootfs/tb138fc-macs.service" "$MNT/etc/systemd/system/"
ln -sf /etc/systemd/system/tb138fc-macs.service "$MNT/etc/systemd/system/multi-user.target.wants/"

# device firmware from the stock image (tools/extract-firmware.sh + tools/package-firmware.sh)
if [ -f "$OUT/firmware-tb138fc.tar.gz" ]; then
  tar -xzf "$OUT/firmware-tb138fc.tar.gz" -C "$MNT"
else
  echo "WARNING: $OUT/firmware-tb138fc.tar.gz missing - no remoteproc/GPU zap firmware" >&2
fi

# root filesystem: the userdata partition, grown to full size on first boot
echo 'PARTLABEL=userdata  /  ext4  rw,relatime,x-systemd.growfs  0 1' > "$MNT/etc/fstab"

# USB NCM gadget for debugging: tablet 172.16.42.1, host gets 172.16.42.2 via DHCP
install -m 755 /dev/stdin "$MNT/usr/local/bin/tb138fc-usb-gadget" <<'EOF'
#!/bin/sh
G=/sys/kernel/config/usb_gadget/g1
[ -d $G ] && exit 0
mkdir -p $G && cd $G
echo 0x1d6b > idVendor; echo 0x0103 > idProduct
mkdir -p strings/0x409 functions/ncm.usb0 configs/c.1/strings/0x409
echo TB138FC > strings/0x409/serialnumber; echo "TB138FC Linux" > strings/0x409/product
# fixed MACs: a new random host MAC each boot would exhaust the DHCP pool
echo 02:7b:13:8f:c0:01 > functions/ncm.usb0/dev_addr
echo 02:7b:13:8f:c0:02 > functions/ncm.usb0/host_addr
ln -s functions/ncm.usb0 configs/c.1/
ls /sys/class/udc | head -1 > UDC
EOF
cat > "$MNT/etc/systemd/system/tb138fc-usb-gadget.service" <<'EOF'
[Unit]
Description=USB NCM debug gadget
After=sys-kernel-config.mount
Before=systemd-networkd.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/tb138fc-usb-gadget

[Install]
WantedBy=multi-user.target
EOF
ln -sf /etc/systemd/system/tb138fc-usb-gadget.service "$MNT/etc/systemd/system/multi-user.target.wants/"
cat > "$MNT/etc/systemd/network/50-usb0.network" <<'EOF'
[Match]
Name=usb0

[Network]
Address=172.16.42.1/24
DHCPServer=yes

[DHCPServer]
PoolOffset=2
PoolSize=8
EOF
mkdir -p "$MNT/etc/NetworkManager/conf.d"
printf '[keyfile]\nunmanaged-devices=interface-name:usb0\n' > "$MNT/etc/NetworkManager/conf.d/usb0.conf"

# kernel modules for our kernel
make -s -C "$KERNEL" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- INSTALL_MOD_PATH="$MNT" INSTALL_MOD_STRIP=1 modules_install
depmod -b "$MNT" "$KVER"

# restore normal pacman behaviour for the device
sed -i '/^DisableSandbox$/d; s/^#CheckSpace/CheckSpace/' "$MNT/etc/pacman.conf"
rm -f "$MNT/etc/resolv.conf"; ln -sf /run/systemd/resolve/stub-resolv.conf "$MNT/etc/resolv.conf"
bash "$REPO/rootfs/customize.sh" "$MNT"   # fonts and other user-facing defaults
du -sh "$MNT"
cleanup
trap - EXIT
e2fsck -fy "$IMG" >/dev/null || true
e2fsck -fn "$IMG"
img2simg "$IMG" "$OUT/rootfs.simg"
ls -l "$OUT/rootfs.simg"
echo "ROOTFS DONE ($KVER)"
