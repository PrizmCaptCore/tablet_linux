# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import contextlib
import os
import shutil
import signal
from pathlib import Path

from tbctl.core.process import BuildError, run, run_quiet

KERNEL_FS = ("proc", "sys", "dev", "dev/pts")


@contextlib.contextmanager
def loop_mounted(image: Path, mountpoint: Path, readonly: bool = False):
    opts = "loop,ro,noload" if readonly else "loop"
    if not image.is_file():
        raise BuildError(f"no such image: {image}")
    mountpoint.mkdir(parents=True, exist_ok=True)
    run(["mount", "-o", opts, str(image), str(mountpoint)])
    try:
        yield mountpoint
    finally:
        run_quiet(["umount", "-l", str(mountpoint)])


def kill_processes_in(root: Path) -> None:
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


def in_chroot(root: Path, script: str, stdin: str | None = None) -> None:
    run(["chroot", str(root), "/bin/bash", "-eo", "pipefail", "-c", script], input=stdin,
        text=stdin is not None)
