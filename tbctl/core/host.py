# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path

from tbctl.core.config import build_user_home
from tbctl.core.process import BuildError


def require_linux_root() -> list[str]:
    problems = []
    if platform.system() != "Linux":
        problems.append("must run on Linux (on Windows: inside WSL)")
    elif os.geteuid() != 0:
        problems.append("must run as root (loop mounts and chroot)")
    return problems


def require_tools(tools: list[str]) -> list[str]:
    missing = [t for t in tools if shutil.which(t) is None]
    return ["missing tools: " + ", ".join(missing)] if missing else []


def require_aarch64_exec() -> list[str]:
    if platform.machine() in ("aarch64", "arm64"):
        return []
    binfmt = Path("/proc/sys/fs/binfmt_misc/qemu-aarch64")
    info = binfmt.read_text() if binfmt.exists() else ""
    flags = next((l.split(":", 1)[1].strip() for l in info.splitlines()
                  if l.startswith("flags:")), "")
    if "enabled" not in info:
        return ["aarch64 binaries cannot run here: install qemu-user + qemu-user-binfmt"]
    if "F" not in flags:
        return ["qemu-aarch64 binfmt lacks the F flag (use qemu-user-binfmt)"]
    return []


def ensure(problems: list[str]) -> None:
    if problems:
        raise BuildError("host not ready:\n  - " + "\n  - ".join(problems))


def give_back(*paths: Path) -> None:
    if os.geteuid() != 0:
        return
    st = build_user_home().stat()
    for top in paths:
        if not top.exists():
            continue
        for p in [top, *(top.rglob("*") if top.is_dir() else [])]:
            os.lchown(p, st.st_uid, st.st_gid)


def enter_private_mount_namespace() -> None:
    if os.environ.get("TBCTL_UNSHARED"):
        return
    env = dict(os.environ, TBCTL_UNSHARED="1")
    os.execvpe("unshare", ["unshare", "-m", "--propagation", "private", *sys.orig_argv], env)
