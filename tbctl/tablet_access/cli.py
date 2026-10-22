# SPDX-License-Identifier: GPL-2.0-only
"""Tablet commands (run natively on the PC, Windows or Linux):

    tbctl run [--root] CMD...          tbctl push FILE... DIR      tbctl pull REMOTE [LOCAL]
    tbctl shell                        tbctl reboot [--bootloader] [--no-wait]
    tbctl flash boot [IMAGE]           tbctl flash rootfs [IMAGE] --wipe-userdata
    tbctl rescue run CMD...            tbctl rescue push FILE REMOTE
    tbctl debug regs [-o FILE]         tbctl debug gpu
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path, PurePosixPath

from tbctl.core.config import load
from tbctl.core.process import BuildError, log
from tbctl.tablet_access import debug, fastboot, rescue, ssh


def _command(args: argparse.Namespace) -> str:
    return " ".join(args.cmd) if args.cmd else sys.stdin.read()


def _run(args: argparse.Namespace) -> int:
    with ssh.Session() as s:
        return s.run(_command(args), root=args.root, timeout=args.timeout)


def _remote(path: str) -> str:
    """A tablet path must be absolute POSIX. Git Bash rewrites /tmp, /home/... arguments into
    Windows paths before tbctl sees them."""
    if not path.startswith("/"):
        raise BuildError(f"tablet path {path!r} is not an absolute Linux path"
                         " (from Git Bash: set MSYS_NO_PATHCONV=1 or write //tmp)")
    return path


def _push(args: argparse.Namespace) -> int:
    with ssh.Session() as s:
        for f in args.files:
            dst = str(PurePosixPath(_remote(args.dir)) / f.name)
            s.put(f, dst)
            print(f"{f} -> {dst} ({f.stat().st_size} bytes)")
    return 0


def _pull(args: argparse.Namespace) -> int:
    local = args.local or Path(PurePosixPath(_remote(args.remote)).name)
    with ssh.Session() as s:
        s.get(args.remote, local)
    print(f"{args.remote} -> {local}")
    return 0


def _reboot(args: argparse.Namespace) -> int:
    fastboot.reboot_linux(bootloader=args.bootloader)
    if args.bootloader:
        fastboot.wait_for_fastboot()
        log("tablet in fastboot")
    elif not args.no_wait:
        log(f"tablet up after {fastboot.wait_for_linux():.0f}s")
    return 0


def _flash(args: argparse.Namespace) -> int:
    out = load().out
    if args.target == "rootfs":
        if not args.wipe_userdata:
            raise BuildError("flashing the rootfs replaces userdata (the whole Arch system and "
                             "home directories); pass --wipe-userdata to confirm")
        image, partition = args.image or out / "rootfs.simg", fastboot.ROOTFS_PARTITION
    else:
        image, partition = args.image or out / "boot.img", fastboot.BOOT_PARTITION
    if not image.is_file():
        raise BuildError(f"no such image: {image}")
    fastboot.enter_fastboot()
    fastboot.flash(partition, image)
    if args.no_reboot:
        return 0
    fastboot.reboot_from_fastboot()
    log(f"tablet up after {fastboot.wait_for_linux(timeout=180):.0f}s")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    r = sub.add_parser("run", help="run a command on the tablet over ssh (stdin if no CMD)")
    r.add_argument("--root", action="store_true", help="through sudo")
    r.add_argument("--timeout", type=float, default=600)
    r.add_argument("cmd", nargs=argparse.REMAINDER)
    r.set_defaults(func=_run)

    p = sub.add_parser("push", help="copy files to a directory on the tablet (sftp)")
    p.add_argument("files", nargs="+", type=Path)
    p.add_argument("dir")
    p.set_defaults(func=_push)

    g = sub.add_parser("pull", help="copy a file from the tablet (sftp)")
    g.add_argument("remote")
    g.add_argument("local", nargs="?", type=Path)
    g.set_defaults(func=_pull)

    sh = sub.add_parser("shell", help="interactive ssh shell")
    sh.set_defaults(func=lambda args: ssh.interactive_shell())

    rb = sub.add_parser("reboot", help="reboot the tablet and wait for it")
    rb.add_argument("--bootloader", action="store_true", help="into fastboot")
    rb.add_argument("--no-wait", action="store_true")
    rb.set_defaults(func=_reboot)

    f = sub.add_parser("flash", help="flash an image (enters fastboot if needed)")
    f.add_argument("target", choices=("boot", "rootfs"))
    f.add_argument("image", nargs="?", type=Path, help="default: out/boot.img, out/rootfs.simg")
    f.add_argument("--wipe-userdata", action="store_true", help="confirm flashing the rootfs")
    f.add_argument("--no-reboot", action="store_true")
    f.set_defaults(func=_flash)

    rs = sub.add_parser("rescue", help="the rescue initramfs (telnet, no rootfs)")
    rcmds = rs.add_subparsers(dest="command", required=True)
    rr = rcmds.add_parser("run")
    rr.add_argument("cmd", nargs=argparse.REMAINDER)
    rr.set_defaults(func=lambda args: print(rescue.run(_command(args))))
    rp = rcmds.add_parser("push")
    rp.add_argument("file", type=Path)
    rp.add_argument("remote")
    rp.add_argument("--mode", default="755")
    rp.set_defaults(func=lambda args: print(rescue.push(args.file, _remote(args.remote), args.mode)))

    d = sub.add_parser("debug", help="debug helpers")
    dcmds = d.add_subparsers(dest="command", required=True)
    dr = dcmds.add_parser("regs", help="dump display-path registers")
    dr.add_argument("-o", "--output", type=Path, default=Path("disp-regs.txt"))
    dr.set_defaults(func=lambda args: debug.display_registers(args.output))
    dg = dcmds.add_parser("gpu", help="is GNOME rendering on the GPU?")
    dg.set_defaults(func=lambda args: debug.gpu_status())
