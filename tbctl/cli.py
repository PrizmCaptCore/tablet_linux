# SPDX-License-Identifier: GPL-2.0-only
"""Command line entry point: `tbctl <group> <command> ...`.

Each command group lives in its own module and registers its subcommands through a
`register(subparsers)` function; every subcommand sets `func` to its handler.
"""
from __future__ import annotations

import argparse
import sys

from tbctl.core.process import BuildError
from tbctl.distro.archlinux import cli as archlinux_cli

GROUPS = (archlinux_cli,)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tbctl", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="group", required=True)
    for group in GROUPS:
        group.register(sub)
    args = ap.parse_args(argv)
    try:
        args.func(args)
    except BuildError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0
