# SPDX-License-Identifier: GPL-2.0-only
"""pacman inside a qemu-user chroot."""
from __future__ import annotations

import contextlib
from pathlib import Path


def relax(conf: str) -> str:
    """Under qemu-user/WSL pacman's Landlock sandbox is unavailable and its disk-space
    check fails: disable both."""
    lines = [("#" + l if l.startswith("CheckSpace") else l)
             for l in conf.splitlines() if l.strip() != "DisableSandbox"]
    return "\n".join(lines).replace("[options]", "[options]\nDisableSandbox", 1) + "\n"


@contextlib.contextmanager
def relaxed_pacman(root: Path):
    """Relax pacman.conf for the build only; the image ships the original."""
    conf = root / "etc/pacman.conf"
    original = conf.read_text()
    conf.write_text(relax(original))
    try:
        yield
    finally:
        conf.write_text(original)
