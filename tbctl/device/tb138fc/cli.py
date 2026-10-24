# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import argparse
from pathlib import Path

from tbctl.device.tb138fc import bootimg, devmap, dts, firmware, initramfs, kernel, panel


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

    f = sub.add_parser("firmware", help="proprietary files from the stock firmware")
    fcmds = f.add_subparsers(dest="command", required=True)
    for name, help_, func in (("extract", "unpack the stock QFIL package", firmware.extract),
                              ("stock-dt", "split and decompile the stock DTBs", firmware.stock_dt),
                              ("package", "remoteproc/zap/amp firmware tarball", firmware.package),
                              ("hexagonfs", "SLPI sensor file tree tarball", firmware.hexagonfs)):
        fc = fcmds.add_parser(name, help=help_)
        fc.set_defaults(func=lambda a, func=func: print(func()), runs_on="linux")
    fd = fcmds.add_parser("devmap", help="device map of the stock overlay -> out/stock-devmap.txt")
    fd.set_defaults(func=lambda a: print(devmap.generate()), runs_on="linux")

    c = kcmds.add_parser("config", help="show kernel config symbols")
    c.add_argument("--tree", type=Path, help="kernel tree (default: <work>/linux)")
    c.add_argument("symbols", nargs="+")
    c.set_defaults(func=lambda a: print("\n".join(kernel.config_values(_tree(a), a.symbols))),
                   runs_on="linux")
