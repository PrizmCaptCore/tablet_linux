# SPDX-License-Identifier: GPL-2.0-only
"""Summarize a built image (read-only mount)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from tbctl.core import host
from tbctl.core.chroot import loop_mounted


def summary(root: Path) -> dict[str, str]:
    release = dict(l.split("=", 1) for l in (root / "etc/os-release").read_text().splitlines()
                   if "=" in l)
    # local db entries are <name>-<pkgver>-<pkgrel>
    pkgs = {p.name.rsplit("-", 2)[0] for p in (root / "var/lib/pacman/local").iterdir()
            if p.is_dir()}
    units = root / "etc/systemd/system"
    enabled = sorted({p.name for p in units.glob("*.wants/*")})
    if (units / "display-manager.service").exists():
        enabled.append("display-manager -> " + os.readlink(units / "display-manager.service"))
    return {
        "release": release.get("PRETTY_NAME", "?").strip('"'),
        "packages": str(len(pkgs)),
        "stock kernel": str("linux-aarch64" in pkgs),
        "gnome-shell / gdm": f"{'gnome-shell' in pkgs} / {'gdm' in pkgs}",
        "hostname": (root / "etc/hostname").read_text().strip(),
        "locale": (root / "etc/locale.conf").read_text().strip(),
        "timezone": os.readlink(root / "etc/localtime"),
        "d2coding": str((root / "usr/share/fonts/d2coding").is_dir()),
        "pacman sandbox": "disabled" if "\nDisableSandbox" in (root / "etc/pacman.conf").read_text() else "default",
        "enabled units": ", ".join(enabled),
    }


def inspect(image: Path) -> None:
    host.ensure(host.require_linux_root())
    host.enter_private_mount_namespace()
    with tempfile.TemporaryDirectory(prefix="tbctl-") as tmp:
        with loop_mounted(image, Path(tmp), readonly=True) as root:
            for key, value in summary(root).items():
                print(f"{key:18}: {value}")
