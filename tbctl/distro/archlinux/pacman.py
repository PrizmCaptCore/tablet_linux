# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import contextlib
from pathlib import Path


def relax(conf: str) -> str:
    lines = [("#" + l if l.startswith("CheckSpace") else l)
             for l in conf.splitlines() if l.strip() != "DisableSandbox"]
    return "\n".join(lines).replace("[options]", "[options]\nDisableSandbox", 1) + "\n"


def unrelax(conf: str, original: str) -> str:
    lines = conf.splitlines()
    if "DisableSandbox" not in original.splitlines():
        lines.remove("DisableSandbox")
    if any(l.startswith("CheckSpace") for l in original.splitlines()):
        lines = [l[1:] if l.startswith("#CheckSpace") else l for l in lines]
    return "\n".join(lines) + "\n"


@contextlib.contextmanager
def relaxed_pacman(root: Path):
    conf = root / "etc/pacman.conf"
    original = conf.read_text()
    conf.write_text(relax(original))
    try:
        yield
    finally:
        conf.write_text(unrelax(conf.read_text(), original))
