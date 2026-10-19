# Shared paths for the TB138FC build scripts. Source this from WSL (bash) scripts.
# Current Development Environment:
# In my case, I use this repo on windows 11, and build by WSL2 so location is fixed, but if you want to use this repo on other environment, please modify the path below.
#   REPO  - this repository (sources, docs, backups) on the Windows E: drive
#   WORK  - WSL-native work dir (kernel tree, initramfs staging, rootfs image); kept in
#           the Linux filesystem because building on /mnt/e is much slower
#   OUT   - build outputs that the Windows-side tools flash (boot.img, rootfs sparse image)
REPO=/mnt/e/windows_project/tablet_linux
WORK=$HOME/tb138fc
OUT=$REPO/out
KERNEL=$WORK/linux
DTS_NAME=sm8250-lenovo-tb138fc
ALPINE_BRANCH=v3.24
export ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-
mkdir -p "$OUT"
