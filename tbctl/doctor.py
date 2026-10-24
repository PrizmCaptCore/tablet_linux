# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import argparse
from pathlib import Path

from tbctl.core import host
from tbctl.core.config import CONFIG_FILE, load
from tbctl.device.tb138fc import bootimg, firmware, initramfs, kernel, panel
from tbctl.distro.archlinux.build import REQUIRED_TOOLS as ROOTFS_TOOLS

STEPS = {
    "kernel": kernel.REQUIRED_TOOLS,
    "initramfs": initramfs.REQUIRED_TOOLS,
    "bootimg": bootimg.REQUIRED_TOOLS,
    "panel": panel.REQUIRED_TOOLS,
    "firmware": firmware.REQUIRED_TOOLS,
    "rootfs": ROOTFS_TOOLS,
}


def _status(problems: list[str]) -> str:
    return "ok" if not problems else "; ".join(problems)


def doctor(args: argparse.Namespace) -> None:
    cfg = load()
    print(f"config         : {CONFIG_FILE if CONFIG_FILE.exists() else 'defaults (no config.toml)'}")
    for name in ("work", "out", "backup", "stock_firmware"):
        p: Path | None = getattr(cfg, name)
        state = "not set" if p is None else ("ok" if p.exists() else "missing")
        print(f"  {name:13}: {p} ({state})")
    print(f"aarch64 exec   : {_status(host.require_aarch64_exec())}")
    for step, tools in STEPS.items():
        print(f"step {step:10}: {_status(host.require_tools(list(tools)))}")


def register(sub: argparse._SubParsersAction) -> None:
    d = sub.add_parser("doctor", help="check the build host (tools, paths)")
    d.set_defaults(func=doctor, runs_on="linux", root=False)
