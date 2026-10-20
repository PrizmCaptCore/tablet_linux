# Mainline Linux on Lenovo Xiaoxin Pad Pro 2022 (TB138FC)

Arch Linux ARM + GNOME on the Snapdragon 870 (SM8250) Xiaoxin Pad Pro 2022, using a mainline
kernel (7.2.11) and a device tree derived from the Xiaoxin Pad Pro 2021 (J716F) and
Pad Pro 12.6 (Q706F) ports.

## Status

| Block | State | Notes |
|---|---|---|
| Boot (abl → kernel) | ✅ | image flashed to `boot_a`; `dtbo_a` erased |
| UFS storage | ✅ | |
| USB (peripheral, NCM debug network) | ✅ | tablet `172.16.42.1` |
| Display (RM692H0, dual DSI, DSC) | ✅ | msm DRM + `kernel/panel/panel-raydium-rm692h0.c`, command mode, 120 Hz (`refresh=60` option), DCS brightness 0-2047 |
| GPU (Adreno 650) | ✅ | Freedreno/GBM; GNOME renders on the GPU |
| Touchscreen (Goodix GT9966S) | ✅ | `goodix,gt9916` on spi0, GPIO chip-select |
| Fuel gauge (bq27541) | ✅ | i2c15 |
| Buttons | ✅ | power, volume up/down |
| Arch Linux ARM + GNOME | ✅ | GDM, touch login, D2Coding everywhere |
| Wi-Fi (QCA6390, ath11k) | ✅ | stock linux-firmware board-2.bin; NTP time sync |
| Bluetooth (QCA6390) | ✅ | power on + scan verified; BD address from fpinfo (`tb138fc-macs`) |
| Remoteprocs (ADSP, CDSP, SLPI) | ✅ | stock firmware (`tools/package-firmware.sh`) |
| Sensors (SLPI: ICM4x6xx accel, AK0991x compass, light) | ✅ | hexagonrpcd (+registry write patches) → libssc → iio-sensor-proxy; auto-rotate verified |
| Speakers (4× CS35L43, ADSP) | ✅ | vendored CS35L43 driver + factory calibration, primary MI2S, UCM `rootfs/ucm2/`; stereo verified |
| Charging (PM8150B SMB5 main charger) | ✅ | qcom_smbx + SMB5 series (kernel/patches 0004-0013): 4.45 V float, 2.4 A; input follows Type-C/PD (5 V, up to 3 A) via `tb138fc-usb-icl`; no fast charge (SMB1396/1398 charge pumps) |
| USB-C (PM8150B TCPM, NB7VPQ904M redriver) | ✅ | dual role: device (NCM debug) / host + OTG VBUS (USB-C earphones verified); PD sink 5 V; DP alt mode (external monitor) verified: 4K30 over a 2-lane USB-C/HDMI hub, repeated plug/unplug OK |
| RTC / clock | ✅ | PM8150 RTC is read-only: `tb138fc-rtc` keeps the offset (clock was 1970 until NTP -> HTTPS errors) |
| Microphone (WCD938x analog, amic1) | ✅ | WCD938x on SoundWire + TX macro, UCM "Mic"; verified in GNOME |

Details: [docs/HARDWARE.md](docs/HARDWARE.md) · history and lessons: [docs/PROGRESS.md](docs/PROGRESS.md) ·
restoring Android / unbricking: [docs/RECOVERY.md](docs/RECOVERY.md)

### notice
most driver came from out of this repo, so I think some of the driver can't work well like revision model and so on.
## Layout

```
env.sh                    shared paths for the WSL build scripts (Just my case, not all of yours. If you want to use other case, than modify this file.)
dts/                      sm8250-lenovo-tb138fc.dts + generator (from J716F) + reference DTS
kernel/                   buildkernel.sh (config + build), mkboot.sh (boot.img for boot_a),
                          panel/ (RM692H0 driver + generator), patches/ (applied by buildkernel.sh)
initramfs/                init (switch to Arch, or debug shell), helper sources, builder
rootfs/                   mkrootfs.sh (Arch Linux ARM + GNOME image → out/rootfs.simg),
                          customize.sh (fonts), install-qbootctl.sh (A/B slot success),
                          tb138fc-macs(.service) (BT/Wi-Fi addresses from fpinfo)
tools/                    deploy.sh, tssh.py/tput.py (ssh/sftp), tsh.py/tpush.py (initramfs),
                          firmware extract/package, disp-regdump.sh, gpu-check.sh, devmap.py, ...
docs/                     hardware notes, stock device map, decompiled stock DT
logs/                     notable logs (UEFI/abl log, first Linux boot log, GPT dump, display
                          register dumps: bootloader vs msm in logs/regs/)
out/                      build outputs (not source)
```

Kept outside this folder (large or path-bound):

| What | Where |
|---|---|
| Stock ZUI 14 QFIL firmware (zip + extracted, ~12 GB) | `C:\Users\PrizmBlue\tb138fc\TB138FC_ZUI14_qpst.zip`, `...\zui14\image\` |
| bkerler/edl + Python venv (EDL flashing) | `C:\Users\PrizmBlue\tb138fc\edl`, `...\venv` |
| Kernel tree, initramfs staging, rootfs image | WSL `Ubuntu-26.04`: `~/tb138fc/` |
| adb / fastboot | `%LOCALAPPDATA%\Android\platform-tools` |

## Build (WSL Ubuntu-26.04)

Host packages: `build-essential gcc-aarch64-linux-gnu bc bison flex libssl-dev libelf-dev
device-tree-compiler cpio lz4 zstd xz-utils mkbootimg android-sdk-libsparse-utils
libarchive-tools qemu-user qemu-user-binfmt`.

```bash
cd /mnt/e/windows_project/tablet_linux
python3 dts/make_tb138fc_dts.py        # regenerate the DTS after editing the generator
bash tools/extract-firmware.sh <zui14/image>  # once: stock firmware → ~/tb138fc/stock-fw
bash tools/package-firmware.sh         # out/firmware-tb138fc.tar.gz (proprietary, not in git)
bash tools/build-hexagonfs.sh <zui14/image>  # out/hexagonfs-tb138fc.tar.gz (SLPI sensor files)
bash kernel/buildkernel.sh             # Image.gz, DTB, modules (incl. panel driver + patches)
bash initramfs/mkinitramfs.sh          # out/initramfs.cpio.gz
bash kernel/mkboot.sh                  # out/boot.img
sudo bash rootfs/mkrootfs.sh           # out/rootfs.simg (Arch + GNOME, ~30-60 min)
```

From Windows, always run WSL scripts as files (`wsl -d Ubuntu-26.04 -- bash /mnt/e/.../script.sh`):
`wsl.exe` re-parses its arguments with a shell, so inline `$VARS` get expanded too early.
After an interrupted rootfs build: `sudo bash tools/loop-cleanup.sh` (or `wsl --shutdown`);
check an image with `sudo bash tools/inspect-rootfs.sh`.

## Deploy (Windows, Git Bash)

```bash
bash tools/deploy.sh                   # reboot to fastboot if needed, flash boot_a, boot
fastboot flash userdata out/rootfs.simg   # root filesystem (wipes userdata)
python tools/tssh.py 'uptime'          # Arch over ssh (alarm/alarm); TB_HOST=<wifi ip> to use Wi-Fi
python tools/tsh.py 'dmesg | tail'     # debug shell over USB (initramfs fallback)
```

Boot flow: abl → kernel + initramfs → mounts `PARTLABEL=userdata` and `switch_root`s into
Arch; if that fails (or `tb.debug` is on the cmdline) it stays in a busybox debug shell
with USB networking and telnet. Arch also brings up the USB network (`172.16.42.1`, sshd).
Default Arch Linux ARM accounts: `alarm`/`alarm`, `root`/`root` — change them.

## Device state (as of 2026-10-18)

- Bootloader unlocked (ZUI 15 abl has no unlock command; downgraded to ZUI 14 via EDL,
  then `fastboot flashing unlock`).
- `boot_a` = our kernel, `dtbo_a` erased → Android does not boot until restored.
- `tb138fc-boot-success.service` (qbootctl -m) marks slot _a successful each boot; without it abl
  eventually flags the slot unbootable and stops in fastboot (`fastboot set_active a` recovers).
- fastboot: hold Volume Down while powering on. EDL: `fastboot oem reboot-edl`, or
  Volume Up while plugging USB with the tablet off.
