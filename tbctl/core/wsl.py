# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import os
import subprocess

from tbctl.core.config import REPO, load
from tbctl.core.process import BuildError


def _wsl(distro: str) -> list[str]:
    return ["wsl", "-d", distro] if distro else ["wsl"]


def _output(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as e:
        raise BuildError(f"WSL is not usable ({' '.join(cmd)}): {e}") from None


def _check_msys_paths(argv: list[str]) -> None:
    git_root = (os.environ.get("EXEPATH") or r"C:\Program Files\Git\bin").replace("\\", "/")
    git_root = git_root.removesuffix("/").removesuffix("/bin")
    mangled = [a for a in argv if git_root.lower() in a.replace("\\", "/").lower()]
    if mangled:
        raise BuildError("Git Bash turned a Linux path into a Windows one: "
                         f"{', '.join(mangled)}\n"
                         "  run with MSYS_NO_PATHCONV=1, or use a relative path")


def delegate(argv: list[str], root: bool) -> int:
    _check_msys_paths(argv)
    base = _wsl(load().wsl_distro)
    linux_repo = _output(base + ["--exec", "wslpath", "-a", str(REPO)])
    home = _output(base + ["--exec", "sh", "-c", "echo $HOME"])
    cmd = base + (["-u", "root"] if root else []) + [
        "--cd", os.getcwd(), "--exec",
        "env", f"PYTHONPATH={linux_repo}", f"TBCTL_HOME={home}",
        "python3", "-m", "tbctl", *argv,
    ]
    return subprocess.call(cmd)
