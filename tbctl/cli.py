# SPDX-License-Identifier: GPL-2.0-only
"""Command line entry point: `tbctl <group> <command> ...`.

Each command group lives in its own module and registers its subcommands through a
`register(subparsers)` function. Every subcommand sets `func` (its handler, returning an
exit status or None) and may set `runs_on="linux"` (build steps; re-run inside WSL when started on Windows) and `root=True`
(needs root, e.g. loop mounts).
"""
from __future__ import annotations

import argparse
import os
import sys

from tbctl import doctor
from tbctl.core import wsl
from tbctl.core.process import BuildError
from tbctl.device.tb138fc import cli as tb138fc_cli
from tbctl.device.tb138fc import full_install
from tbctl.distro.archlinux import cli as archlinux_cli
from tbctl.tablet_access import cli as tablet_access_cli

GROUPS = (doctor, archlinux_cli, tb138fc_cli, tablet_access_cli, full_install)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(prog="tbctl", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="group", required=True)
    for group in GROUPS:
        group.register(sub)
    args = ap.parse_args(argv)
    try:
        if os.name == "nt" and getattr(args, "runs_on", None) == "linux":
            return wsl.delegate(argv, root=getattr(args, "root", False))
        return args.func(args) or 0
    except BuildError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
