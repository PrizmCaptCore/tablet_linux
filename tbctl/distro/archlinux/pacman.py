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


def unrelax(conf: str, original: str) -> str:
    """Undo relax() on `conf`, keeping whatever else the build changed (e.g. IgnorePkg)."""
    lines = conf.splitlines()
    if "DisableSandbox" not in original.splitlines():
        lines.remove("DisableSandbox")
    if any(l.startswith("CheckSpace") for l in original.splitlines()):
        lines = [l[1:] if l.startswith("#CheckSpace") else l for l in lines]
    return "\n".join(lines) + "\n"


@contextlib.contextmanager
def relaxed_pacman(root: Path):
    """Relax pacman.conf for the build only; the image ships it unrelaxed (with any other
    changes the build made)."""
    conf = root / "etc/pacman.conf"
    original = conf.read_text()
    conf.write_text(relax(original))
    try:
        yield
    finally:
        conf.write_text(unrelax(conf.read_text(), original))
