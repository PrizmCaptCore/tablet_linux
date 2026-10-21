# SPDX-License-Identifier: GPL-2.0-only
"""Run tbctl's Linux-only commands inside WSL when started on Windows.

The command is re-run as `python3 -m tbctl <same arguments>` from this repository (mounted
under /mnt/<drive>) in the same working directory, so relative paths keep their meaning.
Root commands use `wsl -u root`, which needs no password. Everything goes through
`wsl --exec` (no shell in between), so Windows paths and quoted arguments arrive intact.
"""
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
    """Git Bash rewrites /home/... arguments into C:/Program Files/Git/home/..., which would
    then be used inside WSL (it once built a 16 GB image in the wrong place)."""
    # EXEPATH: Git Bash's bin directory (C:\Program Files\Git\bin by default)
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
    home = _output(base + ["--exec", "sh", "-c", "echo $HOME"])   # the build user's home
    cmd = base + (["-u", "root"] if root else []) + [
        "--cd", os.getcwd(), "--exec",
        "env", f"PYTHONPATH={linux_repo}", f"TBCTL_HOME={home}",
        "python3", "-m", "tbctl", *argv,
    ]
    return subprocess.call(cmd)
