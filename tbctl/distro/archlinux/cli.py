# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import argparse
import importlib
from pathlib import Path

from tbctl.core import host
from tbctl.core.config import load
from tbctl.distro.archlinux import fonts
from tbctl.distro.archlinux.build import build
from tbctl.distro.archlinux.config import ImageConfig
from tbctl.distro.archlinux.inspect import inspect

DEVICES = {"tb138fc": "tbctl.device.tb138fc.rootfs"}


def _build(args: argparse.Namespace) -> None:
    host.ensure(host.require_linux_root())
    host.enter_private_mount_namespace()
    cfg = load()
    device = importlib.import_module(DEVICES[args.device]) if args.device else None
    plain = ImageConfig(output=Path())

    def setting(name: str):
        value = getattr(args, name)
        if value not in (None, []):
            return value
        if name in cfg.rootfs:
            return cfg.rootfs[name]
        if device and name in device.DEFAULTS:
            return device.DEFAULTS[name]
        return getattr(plain, name)

    output = args.output or (cfg.work / "rootfs.img" if device else None)
    if output is None:
        raise SystemExit("tbctl rootfs build: -o/--output is required without --device")
    sparse = args.sparse or (cfg.out / "rootfs.simg" if device else None)
    image = ImageConfig(
        output=output.resolve(), sparse=sparse.resolve() if sparse else None,
        size=setting("size"), label=setting("label"),
        cache=args.cache or cfg.work / "dl", hostname=setting("hostname"),
        locale=setting("locale"), timezone=setting("timezone"), fonts=list(setting("fonts")),
        packages=args.packages, services=args.services, drop_kernel=args.drop_kernel,
        overlays=[p.resolve() for p in args.overlays],
        overlay_tars=[p.resolve() for p in args.overlay_tars],
        chroot_scripts=[p.resolve() for p in args.chroot_scripts])
    if device:
        if cfg.tablet_user != "alarm":
            image.account = (cfg.tablet_user, cfg.tablet_password)
        image = device.layer(image)
        if args.gamemode:
            if not hasattr(device, "gamemode"):
                raise SystemExit(f"tbctl rootfs build: no game mode for {args.device}")
            image = device.gamemode(image)
    elif args.gamemode:
        raise SystemExit("tbctl rootfs build: --gamemode needs --device")
    build(image)


def register(sub: argparse._SubParsersAction) -> None:
    group = sub.add_parser("rootfs", help="Arch Linux ARM + GNOME root filesystem image")
    cmds = group.add_subparsers(dest="command", required=True)

    b = cmds.add_parser("build", help="build an image (Linux, root)")
    b.add_argument("--device", choices=sorted(DEVICES), help="add the device layer")
    b.add_argument("--gamemode", action="store_true",
                   help="with --device: boot into Steam (gamescope), GNOME one switch away")
    b.add_argument("-o", "--output", type=Path,
                   help="raw ext4 image to create (default with --device: <work>/rootfs.img)")
    b.add_argument("--sparse", type=Path,
                   help="also write an Android sparse image (default with --device: out/rootfs.simg)")
    b.add_argument("--size")
    b.add_argument("--label", help="ext4 filesystem label")
    b.add_argument("--cache", type=Path, help="download cache (default: <work>/dl)")
    b.add_argument("--hostname")
    b.add_argument("--locale", help="system LANG")
    b.add_argument("--timezone")
    b.add_argument("--fonts", action="append", default=[], choices=sorted(fonts.INSTALLERS),
                   help="make a font the desktop default (repeatable)")
    b.add_argument("--package", dest="packages", action="append", default=[],
                   help="extra package (repeatable)")
    b.add_argument("--enable", dest="services", action="append", default=[],
                   help="extra systemd unit to enable (repeatable)")
    b.add_argument("--drop-kernel", action="store_true",
                   help="remove linux-aarch64 (the board ships its own kernel)")
    b.add_argument("--overlay", dest="overlays", action="append", type=Path, default=[],
                   help="copy a directory tree into / (repeatable)")
    b.add_argument("--overlay-tar", dest="overlay_tars", action="append", type=Path, default=[],
                   help="extract a tarball into / (repeatable)")
    b.add_argument("--chroot-script", dest="chroot_scripts", action="append", type=Path,
                   default=[], help="run a shell script inside the image (repeatable)")
    b.set_defaults(func=_build, runs_on="linux", root=True)

    i = cmds.add_parser("inspect", help="summarize an image (Linux, root)")
    i.add_argument("image", type=Path)
    i.set_defaults(func=lambda args: inspect(args.image.resolve()), runs_on="linux", root=True)
