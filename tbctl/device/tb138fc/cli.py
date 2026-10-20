# SPDX-License-Identifier: GPL-2.0-only
"""TB138FC build steps:

    tbctl dts                          dts/sm8250-lenovo-tb138fc.dts from the J716F tree
    tbctl panel driver                 panel-raydium-rm692h0.c from template + init sequence
    tbctl panel init-sequence          rm692h0-init.inc from the stock DT (Linux)
"""
from __future__ import annotations

import argparse

from tbctl.device.tb138fc import dts, panel


def _dts(args: argparse.Namespace) -> None:
    print(f"{dts.OUTPUT}: {dts.generate()} diff lines against {dts.REFERENCE.name}")


def _panel_driver(args: argparse.Namespace) -> None:
    print(f"{panel.DRIVER}: {panel.render_driver()} init commands")


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
