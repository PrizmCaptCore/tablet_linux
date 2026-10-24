# tablet-steamOS

## Installing

### 1. What you need

- **An unlocked bootloader** that accepts `fastboot flash`. Unlocking is out of scope here:
  this project starts from an already unlocked tablet.
  Flashing replaces userdata (Android and its data are gone), and Android stops booting
  (`dtbo_a` is erased).
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

### 3. Build and flash in one go

```bash
tbctl tb138fc full_install                   # every step below, game mode included; images in out/
tbctl tb138fc full_install --wipe-userdata   # ... and flash them (replaces everything on the tablet)
```

The image boots straight into Steam (Big Picture on gamescope, SteamOS style); Steam's "Switch
to Desktop" goes to GNOME and the "Return to Game Mode" app comes back. `--no-gamemode` builds
the plain GNOME image instead, `--from STEP` resumes after a failure. The login is the `.env`
account (`ID=` / `PW=`, root gets the same password) or `alarm` / `alarm` without one. Game mode
adds gtk2 and a patched gamescope (built with makepkg inside the image) and FEX, all cached in
`<work>/pkgcache` after the first build, plus Valve's ARM64 Steam client.

### 3a. Build step by step

```bash
tbctl firmware extract                 # stock QFIL package → <work>/stock-fw
tbctl firmware package                 # out/firmware-tb138fc.tar.gz
tbctl firmware hexagonfs               # out/hexagonfs-tb138fc.tar.gz (SLPI sensor files)
tbctl kernel build                     # Image.gz, DTB, modules (~5 min)
tbctl initramfs                        # out/initramfs.cpio.gz
tbctl bootimg                          # out/boot.img
tbctl rootfs build --device tb138fc    # out/rootfs.simg: Arch + GNOME + device layer (~12 min)
                                       #   --gamemode: + Steam game mode
```

Hostname, locale, timezone and fonts come from `[rootfs]` in `config.toml` (for example
`fonts = ["d2coding"]` makes D2Coding the desktop font everywhere).

### 4. Flash

With the tablet in fastboot (hold Volume Down while powering on) or already running this system:

```bash
tbctl flash boot                       # out/boot.img → boot_a
tbctl flash rootfs --wipe-userdata     # out/rootfs.simg → userdata (~11 min over USB)
```

First boot: log in with the `.env` account, or as `alarm` / `alarm` (`root` / `root`) without
one, and change those. The USB cable doubles
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
      rootfs/                 overlay/ (device files in their install location), gamemode/
                              (Steam session, SDDM), build/ (qbootctl, hexagonrpcd, gamescope
                              patches, built inside the image)
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

Sources:
- `data/kernel/cs35l43/`: CS35L43 amp driver from the Xiaomi Pad 6S Pro mainline port
  ([ianchb/sm8550-mainline](https://github.com/ianchb/sm8550-mainline), branch sheng-7.2.10),
  plus speaker calibration.
- `data/rootfs/build/hexagonrpcd-patches/`: registry write support from the Galaxy Tab S8+ port
  ([aaronsb/sm-x800-linux](https://github.com/aaronsb/sm-x800-linux), PR #37), for hexagonrpc
  commit 598b591.
