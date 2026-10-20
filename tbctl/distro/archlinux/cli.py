# SPDX-License-Identifier: GPL-2.0-only
"""`tbctl rootfs build|inspect`.

    sudo tbctl rootfs build -o rootfs.img --sparse rootfs.simg \\
        --fonts d2coding --locale ko_KR.UTF-8 --timezone Asia/Seoul
    sudo tbctl rootfs inspect rootfs.img
"""
from __future__ import annotations

import argparse
from pathlib import Path

from tbctl.core.config import load
from tbctl.distro.archlinux import fonts
from tbctl.distro.archlinux.build import build
from tbctl.distro.archlinux.config import ImageConfig
from tbctl.distro.archlinux.inspect import inspect


def _build(args: argparse.Namespace) -> None:
    resolve = lambda paths: [p.resolve() for p in paths]  # noqa: E731
    build(ImageConfig(
        output=args.output.resolve(),
        sparse=args.sparse.resolve() if args.sparse else None,
        size=args.size, label=args.label, cache=args.cache or load().work / "dl",
        hostname=args.hostname,
        locale=args.locale, timezone=args.timezone, fonts=args.fonts,
        packages=args.packages, services=args.services, drop_kernel=args.drop_kernel,
        overlays=resolve(args.overlays), overlay_tars=resolve(args.overlay_tars),
        chroot_scripts=resolve(args.chroot_scripts)))


def register(sub: argparse._SubParsersAction) -> None:
    group = sub.add_parser("rootfs", help="Arch Linux ARM + GNOME root filesystem image")
    cmds = group.add_subparsers(dest="command", required=True)
    defaults = ImageConfig(output=Path())

    b = cmds.add_parser("build", help="build an image (Linux, root)")
    b.add_argument("-o", "--output", type=Path, required=True, help="raw ext4 image to create")
    b.add_argument("--sparse", type=Path, help="also write an Android sparse image (fastboot)")
    b.add_argument("--size", default=defaults.size)
    b.add_argument("--label", default=defaults.label, help="ext4 filesystem label")
    b.add_argument("--cache", type=Path, help="download cache (default: <work>/dl)")
    b.add_argument("--hostname", default=defaults.hostname)
    b.add_argument("--locale", default=defaults.locale, help="system LANG")
    b.add_argument("--timezone", default=defaults.timezone)
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
