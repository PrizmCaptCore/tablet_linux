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


def delegate(argv: list[str], root: bool) -> int:
    base = _wsl(load().wsl_distro)
    linux_repo = _output(base + ["--exec", "wslpath", "-a", str(REPO)])
    home = _output(base + ["--exec", "sh", "-c", "echo $HOME"])   # the build user's home
    cmd = base + (["-u", "root"] if root else []) + [
        "--cd", os.getcwd(), "--exec",
        "env", f"PYTHONPATH={linux_repo}", f"TBCTL_HOME={home}",
        "python3", "-m", "tbctl", *argv,
    ]
    return subprocess.call(cmd)
