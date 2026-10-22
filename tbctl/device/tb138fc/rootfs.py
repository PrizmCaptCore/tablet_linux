# SPDX-License-Identifier: GPL-2.0-only
"""The TB138FC layer of the root filesystem image, on top of distro.archlinux:

  rootfs/overlay/         files in their install location (services, udev rules, UCM, ...)
  rootfs/build/*.sh       run in the image chroot: qbootctl, hexagonrpcd (built from source)
  out/firmware-*.tar.gz   stock remoteproc/zap/amp firmware   (tbctl firmware package)
  out/hexagonfs-*.tar.gz  stock SLPI sensor files             (tbctl firmware hexagonfs)
  kernel modules          from the kernel tree                (tbctl kernel build)
  /usr/local/bin/regdump  initramfs/src/regdump.c, for `tbctl debug regs`
"""
from __future__ import annotations

import os
import shutil
from dataclasses import replace
from pathlib import Path

from tbctl.core.config import load
from tbctl.device.tb138fc import DATA
from tbctl.core.host import give_back
from tbctl.core.process import BuildError, run
from tbctl.device.tb138fc import kernel
from tbctl.distro.archlinux.config import ImageConfig

OVERLAY = DATA / "rootfs" / "overlay"
BUILD_SCRIPTS = (DATA / "rootfs/build/qbootctl.sh", DATA / "rootfs/build/hexagonrpcd.sh")
HEXAGONRPCD_PATCHES = DATA / "rootfs/build/hexagonrpcd-patches"
EXECUTABLE_DIRS = ("usr/local/bin",)
# links git cannot be trusted with (Windows checkouts turn symlinks into text files)
SYMLINKS = {
    "usr/share/alsa/ucm2/conf.d/sm8250/Lenovo-TB138FC.conf": "../../Lenovo/TB138FC/TB138FC.conf",
    # system sleep is not verified on this port (masked since bring-up): logind must not try it
    **{f"etc/systemd/system/{t}.target": "/dev/null"
       for t in ("sleep", "suspend", "hibernate", "hybrid-sleep")},
}
STATIC_HELPERS = ("regdump",)           # initramfs/src/<name>.c -> /usr/local/bin/<name>

PACKAGES = ("iio-sensor-proxy", "linux-firmware-qcom", "i2c-tools")
SERVICES = (
    "tb138fc-rtc.service",            # sysinit: system clock from RTC + saved offset
    "tb138fc-rtc-save.path",
    "tb138fc-macs.service",           # Wi-Fi address from fpinfo
    "tb138fc-spk-cal.service",        # speaker calibration from persist
    "tb138fc-bt-watchdog.service",    # QCA6390 BT crash-loop recovery
    "tb138fc-usb-gadget.service",     # USB NCM debug link
    "tb138fc-boot-success.service",   # mark slot a successful (abl)
    "hexagonrpcd-sdsp.service",       # SLPI sensors
    "tb138fc-power-key.service",      # power key: screen toggle / power-off dialog
)
DEFAULTS = {"hostname": "tb138fc", "label": "tb138fc-root"}


def _stage_layer(tree: Path) -> Path:
    """The overlay as it lands in the image: normalized modes, symlinks, helpers, patches."""
    cfg = load()
    stage = cfg.work / "device-layer"
    shutil.rmtree(stage, ignore_errors=True)
    shutil.copytree(OVERLAY, stage, symlinks=True)
    # the checkout's modes are meaningless (Windows/drvfs): set them explicitly
    for path in stage.rglob("*"):
        if path.is_symlink():
            continue
        rel = path.relative_to(stage).as_posix()
        exe = path.is_dir() or any(rel.startswith(d + "/") for d in EXECUTABLE_DIRS)
        path.chmod(0o755 if exe else 0o644)
    stage.chmod(0o755)
    for link, target in SYMLINKS.items():
        (stage / link).parent.mkdir(parents=True, exist_ok=True)
        os.symlink(target, stage / link)
    for name in STATIC_HELPERS:
        run(["aarch64-linux-gnu-gcc", "-static", "-O2", "-o", str(stage / "usr/local/bin" / name),
             str(DATA / "initramfs/src" / f"{name}.c")])
    shutil.copytree(HEXAGONRPCD_PATCHES, stage / "tmp/hexagonrpcd-patches")
    return stage


def _finish_script(kver: str) -> Path:
    script = load().work / "device-finish.sh"
    script.write_text("set -e\n"
                      f"depmod {kver}\n"
                      "dconf update\n"
                      "rm -rf /tmp/hexagonrpcd-patches\n")
    return script


def layer(image: ImageConfig, tree: Path | None = None) -> ImageConfig:
    """`image` with the TB138FC layer added (prerequisites are checked here)."""
    tree = tree or kernel.tree_path()
    out = load().out
    tars = [out / "firmware-tb138fc.tar.gz", out / "hexagonfs-tb138fc.tar.gz"]
    for t, how in zip(tars, ("tbctl firmware package", "tbctl firmware hexagonfs")):
        if not t.is_file():
            raise BuildError(f"missing {t} (run `{how}`)")
    if not (tree / "arch/arm64/boot/Image.gz").is_file():
        raise BuildError(f"no kernel built in {tree} (run `tbctl kernel build`)")
    kver = kernel.kernelrelease(tree)
    modules = kernel.modules_tarball(tree)
    stage, finish = _stage_layer(tree), _finish_script(kver)
    give_back(load().work / "modstage", modules, stage, finish)
    return replace(
        image,
        drop_kernel=True,
        packages=[*image.packages, *PACKAGES],
        services=[*image.services, *SERVICES],
        overlay_tars=[*image.overlay_tars, modules, *tars],
        overlays=[*image.overlays, stage],
        chroot_scripts=[*image.chroot_scripts, *BUILD_SCRIPTS, finish],
    )
