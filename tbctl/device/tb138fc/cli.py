# SPDX-License-Identifier: GPL-2.0-only
"""TB138FC build steps:

    tbctl dts                          dts/sm8250-lenovo-tb138fc.dts from the J716F tree
    tbctl panel driver                 panel-raydium-rm692h0.c from template + init sequence
    tbctl panel init-sequence          rm692h0-init.inc from the stock DT (Linux)
    tbctl kernel build                 Image.gz, DTB, modules (Linux)
    tbctl kernel modules               out/modules-<kver>.tar.gz for a running tablet (Linux)
    tbctl kernel patches               which kernel/patches apply to the tree (Linux)
    tbctl kernel config SYM...         values of kernel config symbols (Linux)
    tbctl initramfs                    out/initramfs.cpio.gz (Linux)
    tbctl bootimg                      out/boot.img from the kernel tree + initramfs (Linux)
"""
from __future__ import annotations

import argparse
from pathlib import Path

from tbctl.device.tb138fc import bootimg, dts, initramfs, kernel, panel


def _dts(args: argparse.Namespace) -> None:
    print(f"{dts.OUTPUT}: {dts.generate()} diff lines against {dts.REFERENCE.name}")


def _panel_driver(args: argparse.Namespace) -> None:
    print(f"{panel.DRIVER}: {panel.render_driver()} init commands")


def _tree(args: argparse.Namespace) -> Path:
    return args.tree.resolve() if args.tree else kernel.tree_path()


def _kernel_patches(args: argparse.Namespace) -> None:
    for name, state in kernel.patch_status(_tree(args)):
        print(f"{state:11} {name}")


def register(sub: argparse._SubParsersAction) -> None:
    d = sub.add_parser("dts", help="generate the TB138FC devicetree source")
    d.set_defaults(func=_dts)

    p = sub.add_parser("panel", help="RM692H0 panel driver")
    pcmds = p.add_subparsers(dest="command", required=True)
    pd = pcmds.add_parser("driver", help="render the driver from template + init sequence")
    pd.set_defaults(func=_panel_driver)
    pi = pcmds.add_parser("init-sequence", help="regenerate the init sequence from the stock DT")
    pi.set_defaults(func=lambda args: print(f"{panel.init_sequence()} init commands"),
                    runs_on="linux")

    k = sub.add_parser("kernel", help="the TB138FC kernel")
    kcmds = k.add_subparsers(dest="command", required=True)
    for name, help_, func in (
            ("build", "fetch, patch, configure and build", lambda a: kernel.build(_tree(a)) and None),
            ("modules", "stripped modules tarball in out/",
             lambda a: print(kernel.modules_tarball(_tree(a)))),
            ("patches", "patch state against the tree", _kernel_patches)):
        c = kcmds.add_parser(name, help=help_)
        c.add_argument("--tree", type=Path, help="kernel tree (default: <work>/linux)")
        c.set_defaults(func=func, runs_on="linux")
    i = sub.add_parser("initramfs", help="build out/initramfs.cpio.gz")
    i.set_defaults(func=lambda a: initramfs.build() and None, runs_on="linux")
    b = sub.add_parser("bootimg", help="build out/boot.img")
    b.add_argument("--tree", type=Path, help="kernel tree (default: <work>/linux)")
    b.set_defaults(func=lambda a: bootimg.build(_tree(a)) and None, runs_on="linux")

    c = kcmds.add_parser("config", help="show kernel config symbols")
    c.add_argument("--tree", type=Path, help="kernel tree (default: <work>/linux)")
    c.add_argument("symbols", nargs="+")
    c.set_defaults(func=lambda a: print("\n".join(kernel.config_values(_tree(a), a.symbols))),
                   runs_on="linux")
