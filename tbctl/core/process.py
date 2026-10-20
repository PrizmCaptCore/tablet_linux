# SPDX-License-Identifier: GPL-2.0-only
"""Running external commands and reporting progress."""
from __future__ import annotations

import subprocess


class BuildError(RuntimeError):
    """A step failed; the CLI prints the message and exits non-zero."""


def log(msg: str) -> None:
    print(f"[tbctl] {msg}", flush=True)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    """Run a command, echoing it; raise BuildError on failure."""
    log("$ " + " ".join(cmd))
    try:
        return subprocess.run(cmd, check=True, **kw)
    except subprocess.CalledProcessError as e:
        raise BuildError(f"command failed ({e.returncode}): {' '.join(cmd)}") from None


def run_quiet(cmd: list[str]) -> int:
    """Run a best-effort command (cleanup), ignoring failure and output."""
    return subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode
