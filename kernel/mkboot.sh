#!/bin/bash
# Package kernel + DTB + initramfs into an Android boot image (header v2) for boot_a.
# Lenovo's abl removed `fastboot boot`, so the image is flashed (tbctl flash boot).
#   bash kernel/mkboot.sh
set -eo pipefail
source "$(dirname "$(readlink -f "$0")")/../env.sh"
K=$KERNEL/arch/arm64/boot
# Offsets match the stock ZUI boot.img. abl appends its own args (androidboot.*, init=/init).
mkbootimg --header_version 2 --os_version 11.0.0 --os_patch_level 2021-10 \
  --kernel $K/Image.gz --ramdisk "$OUT/initramfs.cpio.gz" --dtb "$K/dts/qcom/$DTS_NAME.dtb" \
  --pagesize 4096 --base 0x0 --kernel_offset 0x8000 --ramdisk_offset 0x1000000 \
  --tags_offset 0x100 --dtb_offset 0x1f00000 \
  --cmdline "console=tty0 clk_ignore_unused pd_ignore_unused rdinit=/init" \
  -o "$OUT/boot.img"
ls -l "$OUT/boot.img"
