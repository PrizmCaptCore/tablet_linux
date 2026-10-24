# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import re
import subprocess
import sys


class BuildError(RuntimeError):
    pass


def log(msg: str) -> None:
    print(f"[tbctl] {msg}", flush=True)


def run(cmd: list[str], check: bool = True, **kw) -> subprocess.CompletedProcess:
    log("$ " + " ".join(cmd))
    try:
        return subprocess.run(cmd, check=check, **kw)
    except subprocess.CalledProcessError as e:
        raise BuildError(f"command failed ({e.returncode}): {' '.join(cmd)}") from None


def run_quiet(cmd: list[str]) -> int:
    return subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode


def run_filtered(cmd: list[str], drop: re.Pattern, **kw) -> None:
    log("$ " + " ".join(cmd))
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                          errors="replace", **kw) as p:
        for line in p.stdout:
            if not drop.search(line):
                sys.stdout.write(line)
                sys.stdout.flush()
    if p.returncode != 0:
        raise BuildError(f"command failed ({p.returncode}): {' '.join(cmd)}")
