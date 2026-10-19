#!/bin/bash
# WSL (root): release everything left over from a rootfs build: processes still running
# inside the chroot (gpg-agent/dirmngr from pacman-key), lazy mounts, loop devices.
for p in /proc/[0-9]*; do
  r=$(readlink "$p/root" 2>/dev/null) || continue
  case "$r" in */tb138fc/rootfs-mnt*) echo "killing $(cat $p/comm) (${p#/proc/}) rooted at $r"; kill -9 "${p#/proc/}";; esac
done
sleep 1
grep rootfs-mnt /proc/mounts | awk '{print $2}' | sort -r | xargs -r -n1 umount -l
losetup -a | grep 'tb138fc/rootfs.img' | cut -d: -f1 | xargs -r -n1 losetup -d
echo "remaining loop devices: $(losetup -a | grep -c 'tb138fc/rootfs.img')"
