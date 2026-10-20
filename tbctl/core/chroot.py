# SPDX-License-Identifier: GPL-2.0-only
"""Loop-mounted images and chroots into them."""
from __future__ import annotations

import contextlib
import os
import shutil
import signal
from pathlib import Path

from tbctl.core.process import run, run_quiet

KERNEL_FS = ("proc", "sys", "dev", "dev/pts")


@contextlib.contextmanager
def loop_mounted(image: Path, mountpoint: Path, readonly: bool = False):
    # noload: a read-only mount must not replay the ext4 journal into the image
    opts = "loop,ro,noload" if readonly else "loop"
    mountpoint.mkdir(parents=True, exist_ok=True)
    run(["mount", "-o", opts, str(image), str(mountpoint)])
    try:
        yield mountpoint
    finally:
        run_quiet(["umount", "-l", str(mountpoint)])


def kill_processes_in(root: Path) -> None:
    """Kill everything whose root is inside `root` (daemons started in the chroot, e.g.
    gpg-agent from pacman-key, pin the mounts)."""
    root_s = str(root.resolve())
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if os.readlink(proc / "root").startswith(root_s):
                os.kill(int(proc.name), signal.SIGKILL)
        except OSError:
            pass


@contextlib.contextmanager
def chroot_ready(root: Path):
    """Bind the kernel filesystems and the host's resolv.conf into `root`; undo on exit."""
    for d in KERNEL_FS:
        run(["mount", "--bind", f"/{d}", str(root / d)])
    resolv = root / "etc/resolv.conf"
    link = os.readlink(resolv) if resolv.is_symlink() else None
    resolv.unlink(missing_ok=True)
    shutil.copy("/etc/resolv.conf", resolv)
    try:
        yield root
    finally:
        kill_processes_in(root)
        resolv.unlink(missing_ok=True)
        if link:
            resolv.symlink_to(link)
        for d in reversed(KERNEL_FS):
            run_quiet(["umount", "-l", str(root / d)])


def in_chroot(root: Path, script: str) -> None:
    """Run a bash script inside `root` (strict mode)."""
    run(["chroot", str(root), "/bin/bash", "-eo", "pipefail", "-c", script])
