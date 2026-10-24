# SPDX-License-Identifier: GPL-2.0-only
"""`tbctl tb138fc full_install`: every build step in order, then flash the tablet.

    stock firmware -> firmware tarballs -> kernel -> initramfs -> boot.img
    -> rootfs (Arch + GNOME + TB138FC layer + game mode) -> flash boot and rootfs

Runs on the PC (Windows or Linux); the build steps go through the normal commands, so on
Windows each one runs inside WSL. Flashing replaces userdata, so it only happens with
--wipe-userdata; without it the images are left in out/. --from resumes at a step.
"""
from __future__ import annotations

import argparse

from tbctl.core.config import load
from tbctl.core.process import BuildError, log
from tbctl.tablet_access import fastboot

# step name -> tbctl arguments
STEPS = {
    "doctor": ["doctor"],
    "firmware-extract": ["firmware", "extract"],
    "firmware-package": ["firmware", "package"],
    "hexagonfs": ["firmware", "hexagonfs"],
    "kernel": ["kernel", "build"],
    "initramfs": ["initramfs"],
    "bootimg": ["bootimg"],
    "rootfs": ["rootfs", "build", "--device", "tb138fc", "--gamemode"],
}


def _run_step(argv: list[str]) -> None:
    from tbctl.cli import main            # the CLI imports this module
    if main(argv) != 0:
        raise BuildError(f"step failed: tbctl {' '.join(argv)}")


def full_install(args: argparse.Namespace) -> None:
    cfg = load()
    if cfg.stock_firmware is None and args.start == "doctor":
        raise BuildError("config.toml [build] stock_firmware is not set (the extracted stock "
                         "ZUI QFIL package); see config.example.toml")
    names = list(STEPS)
    for name in names[names.index(args.start):]:
        log(f"=== {name}")
        argv = STEPS[name]
        if name == "rootfs" and args.no_gamemode:
            argv = [a for a in argv if a != "--gamemode"]
        _run_step(argv)
    if not args.wipe_userdata:
        log(f"images ready: {cfg.out / 'boot.img'}, {cfg.out / 'rootfs.simg'}\n"
            "  flash them with --wipe-userdata (replaces everything on the tablet)")
        return
    log("=== flash")
    fastboot.enter_fastboot()
    fastboot.flash(fastboot.ROOTFS_PARTITION, cfg.out / "rootfs.simg")
    fastboot.flash(fastboot.BOOT_PARTITION, cfg.out / "boot.img")
    fastboot.reboot_from_fastboot()
    log(f"tablet up after {fastboot.wait_for_linux(timeout=300):.0f}s")


def register(sub: argparse._SubParsersAction) -> None:
    g = sub.add_parser("tb138fc", help="whole-device operations")
    cmds = g.add_subparsers(dest="command", required=True)
    f = cmds.add_parser("full_install", aliases=["full-install"],
                        help="build everything (game mode included) and flash the tablet")
    f.add_argument("--wipe-userdata", action="store_true",
                   help="flash at the end (replaces the whole Arch system and home directories)")
    f.add_argument("--from", dest="start", choices=list(STEPS), default="doctor",
                   help="resume at this step")
    f.add_argument("--no-gamemode", action="store_true",
                   help="plain GNOME image (GDM login) instead of booting into Steam")
    f.set_defaults(func=full_install)
