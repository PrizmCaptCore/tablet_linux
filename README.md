# Mainline Linux on Lenovo Xiaoxin Pad Pro 2022 (TB138FC)

Arch Linux ARM + GNOME on the Snapdragon 870 (SM8250) Xiaoxin Pad Pro 2022, using a mainline
kernel (7.2.11) and a device tree derived from the Xiaoxin Pad Pro 2021 (J716F) and
Pad Pro 12.6 (Q706F) ports. Everything is built and flashed with one tool, `tbctl`.

## Status

| Block | State | Notes |
|---|---|---|
| Boot (abl → kernel) | ✅ | image flashed to `boot_a`; `dtbo_a` erased |
| UFS storage | ✅ | |
| USB (peripheral, NCM debug network) | ✅ | tablet `172.16.42.1` |
| Display (RM692H0, dual DSI, DSC) | ✅ | msm DRM + `data/kernel/panel/panel-raydium-rm692h0.c`, command mode, 120 Hz (`refresh=60` option), DCS brightness 0-2047 |
| GPU (Adreno 650) | ✅ | Freedreno/GBM; GNOME renders on the GPU |
| Touchscreen (Goodix GT9966S) | ✅ | `goodix,gt9916` on spi0, GPIO chip-select |
| Fuel gauge (bq27541) | ✅ | i2c15 |
| Buttons | ✅ | power, volume up/down |
| Arch Linux ARM + GNOME | ✅ | GDM, touch login |
| Wi-Fi (QCA6390, ath11k) | ✅ | stock linux-firmware board-2.bin; NTP time sync |
| Bluetooth (QCA6390) | ✅ | BD address from fpinfo; crash-loop watchdog; BLE keyboards (uhid) |
| Remoteprocs (ADSP, CDSP, SLPI) | ✅ | stock firmware (`tbctl firmware package`) |
| Sensors (SLPI: ICM4x6xx accel, AK0991x compass, light) | ✅ | hexagonrpcd (+registry write patches) → libssc → iio-sensor-proxy; auto-rotate verified |
| Speakers (4× CS35L43, ADSP) | ✅ | vendored CS35L43 driver + factory calibration, primary MI2S, UCM in `data/rootfs/overlay/usr/share/alsa/ucm2/`; stereo verified |
| Microphone (WCD938x analog, amic1) | ✅ | WCD938x on SoundWire + TX macro, UCM "Mic"; verified in GNOME |
| Charging (PM8150B SMB5 main charger) | ✅ | qcom_smbx + SMB5 series (`data/kernel/patches` 0004-0013): 4.45 V float, 2.4 A; input follows Type-C/PD (5 V, up to 3 A) via `tb138fc-usb-icl`; no fast charge (SMB1396/1398 charge pumps) |
| USB-C (PM8150B TCPM, NB7VPQ904M redriver) | ✅ | dual role: device (NCM debug) / host + OTG VBUS (USB-C earphones verified); PD sink 5 V; DP alt mode (external monitor): 4K30 over a 2-lane USB-C/HDMI hub, repeated plug/unplug OK |
| RTC / clock | ✅ | PM8150 RTC is read-only: `tb138fc-rtc` keeps the offset (correct after the first NTP sync) |
| System sleep (suspend) | ❌ | not verified; the sleep targets are masked |

Several drivers come from outside mainline (vendored or patched, see `data/kernel/`), and only this
one unit has been tested: other hardware revisions of the tablet may differ.

## Installing

### 1. What you need

- **An unlocked bootloader.** ZUI 15 cannot be unlocked; the way that worked.
  Unlocking and flashing wipe the tablet, and Android stops booting (`dtbo_a` is erased).
- **The stock ZUI 14 QFIL package**, extracted (its `image/` directory). Proprietary firmware
  (DSPs, GPU zap shader, amp tunings, sensor configs) is taken from it at build time and never
  committed.
- **EDL dumps of the device-unique partitions** (`persist` at least): the sensor registry is
  built from `persist.img`. Keep them outside the repository (they hold the serial number,
  MACs and calibration data).
- **A Linux host, or Windows with WSL 2** (Ubuntu 26.04 used here), Python 3.11+, and
  `fastboot` (Android platform-tools) on the side the tablet is plugged into.
- Host packages for the build steps (Debian/Ubuntu names):
  `build-essential gcc-aarch64-linux-gnu bc bison flex libssl-dev libelf-dev xz-utils
  device-tree-compiler python3-libfdt cpio mkbootimg android-sdk-libsparse-utils
  libarchive-tools e2fsprogs erofs-utils mtools git qemu-user qemu-user-binfmt`.

### 2. Set up tbctl

```bash
pip install -e .                       # installs the `tbctl` command (or use `python -m tbctl`)
cp config.example.toml config.toml     # then set [build] stock_firmware and backup
tbctl doctor                           # checks paths, host tools and qemu, per build step
```

On Windows, the build steps run inside WSL automatically (`wsl -u root` for the root ones), so
the same commands work from PowerShell. From Git Bash, pass Linux paths with
`MSYS_NO_PATHCONV=1` (or use relative paths): Git Bash rewrites `/home/...` arguments into
Windows paths, and tbctl refuses those.

### 3. Build

```bash
tbctl firmware extract                 # stock QFIL package → <work>/stock-fw
tbctl firmware package                 # out/firmware-tb138fc.tar.gz
tbctl firmware hexagonfs               # out/hexagonfs-tb138fc.tar.gz (SLPI sensor files)
tbctl kernel build                     # Image.gz, DTB, modules (~5 min)
tbctl initramfs                        # out/initramfs.cpio.gz
tbctl bootimg                          # out/boot.img
tbctl rootfs build --device tb138fc    # out/rootfs.simg: Arch + GNOME + device layer (~12 min)
```

Hostname, locale, timezone and fonts come from `[rootfs]` in `config.toml` (for example
`fonts = ["d2coding"]` makes D2Coding the desktop font everywhere).

### 4. Flash

With the tablet in fastboot (hold Volume Down while powering on) or already running this system:

```bash
tbctl flash boot                       # out/boot.img → boot_a
tbctl flash rootfs --wipe-userdata     # out/rootfs.simg → userdata (~11 min over USB)
```

First boot: log in as `alarm` / `alarm` (`root` / `root`) and change both. The USB cable doubles
as a network link (tablet `172.16.42.1`, sshd), which is how tbctl reaches the tablet.

## Working on a running tablet

```bash
tbctl run 'uptime'                     # ssh (--root: through sudo); TB_HOST=<Wi-Fi IP> for Wi-Fi
tbctl push FILE... DIR / tbctl pull REMOTE [LOCAL] / tbctl shell
tbctl reboot [--bootloader]            # waits until the tablet is back
tbctl kernel modules                   # out/modules-<kver>.tar.gz, then push + tar -C / -xzf
tbctl rescue run 'dmesg | tail'        # telnet shell of the initramfs fallback (no rootfs)
tbctl debug regs | gpu                 # display register dump (screen must be on), GPU check
```

Login: `[tablet] user` in `config.toml`, a `.env` file next to it with `ID=` and `PW=` lines
(ignored by git), or `TB_USER` / `TB_PASS`.

Development of the device files themselves:

```bash
tbctl dts                              # regenerate data/dts/ after editing tbctl/device/tb138fc/dts.py
tbctl panel driver                     # panel .c from template + init sequence
tbctl firmware stock-dt                # stock DTBs → <work>/stock (for `tbctl panel init-sequence`)
tbctl firmware devmap                  # out/stock-devmap.txt: bus/GPIO/supply map of the stock overlay
tbctl kernel patches | config SYM...   # patch state, kernel config values
tbctl rootfs inspect IMAGE             # summary of a built image
```

## Layout

```
tbctl/                        the tool (Python)
  core/                       config, processes, WSL, chroot, Android images
  distro/archlinux/           device-neutral Arch Linux ARM + GNOME image (+ data/: fonts)
  device/tb138fc/             build steps: dts, panel, kernel, initramfs, boot image,
                              firmware, rootfs layer
    data/                     what those steps read (below: data/)
      dts/                    sm8250-lenovo-tb138fc.dts (generated) + reference trees in ref/
      kernel/                 tb138fc.config, patches/ (applied in order),
                              panel/ (RM692H0 driver), cs35l43/ (amp driver)
      initramfs/              init (switch to Arch, or rescue shell), static helper sources
      rootfs/                 overlay/ (device files in their install location), build/
                              (qbootctl, hexagonrpcd + patches, built inside the image)
  tablet_access/              ssh, fastboot, rescue shell, debug helpers
config.example.toml           settings template (copy to config.toml)
out/                          build outputs (ignored by git)
```

Boot flow: abl → kernel + initramfs → mounts `PARTLABEL=userdata` and `switch_root`s into
Arch; if that fails (or `tb.debug` is on the cmdline) it stays in a busybox rescue shell with
USB networking and telnet (`tbctl rescue`).

## Device notes

- Lenovo's abl boots slot a only and has no `fastboot boot`: kernels are tested by flashing
  `boot_a`. `tb138fc-boot-success.service` (qbootctl -m) marks the slot successful on every
  boot; without it abl eventually flags it unbootable and stops in fastboot
  (`fastboot set_active a` recovers).
- fastboot: hold Volume Down while powering on. EDL: `fastboot oem reboot-edl`, or Volume Up
  while plugging USB with the tablet off.

## License

GPL-2.0-only (see [LICENSE](LICENSE)), like the kernel code it carries. Patches to other
projects (`data/kernel/patches/`, `data/rootfs/build/hexagonrpcd-patches/`) follow the license of the
project they patch. Firmware extracted from the stock image is Lenovo/Qualcomm property and
is never part of this repository.
