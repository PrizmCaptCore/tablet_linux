#!/bin/bash
# WSL (root): read-only sanity check of ~/tb138fc/rootfs.img
set -e
M=/home/prizmblue/tb138fc/rootfs-mnt; mkdir -p $M
mount -o loop,ro /home/prizmblue/tb138fc/rootfs.img $M; trap 'umount $M' EXIT
echo "modules: $(ls $M/usr/lib/modules)"; echo "fonts: $(ls $M/usr/share/fonts/d2coding | tr '\n' ' ')"
echo "fstab: $(grep -v '^#' $M/etc/fstab)"
echo "enabled: $(ls $M/etc/systemd/system/multi-user.target.wants/ | tr '\n' ' ')"
echo "display-manager: $(readlink $M/etc/systemd/system/display-manager.service)"
echo "init: $(readlink -f $M/sbin/init | sed "s#$M##")"
echo "pacman sandbox line: $(grep -c '^DisableSandbox' $M/etc/pacman.conf)"
