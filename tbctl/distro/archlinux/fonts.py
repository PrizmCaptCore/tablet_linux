# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import zipfile
from importlib import resources
from pathlib import Path

from tbctl.core.chroot import in_chroot
from tbctl.core.fetch import download
from tbctl.distro.archlinux.config import ImageConfig

D2CODING_VERSION = "1.4.0"
D2CODING_BUILD = "20261003"
D2CODING_FILES = (f"D2Coding-Ver{D2CODING_VERSION}-{D2CODING_BUILD}.ttf",
                  f"D2CodingBold-Ver{D2CODING_VERSION}-{D2CODING_BUILD}.ttf")
D2CODING_URL = ("https://github.com/naver/d2-coding-font/releases/download/"
                f"VER{D2CODING_VERSION}/D2Coding-Ver{D2CODING_VERSION}-{D2CODING_BUILD}.zip")


def _data(name: str) -> str:
    return resources.files(__package__).joinpath("data", name).read_text()


def install_d2coding(root: Path, cfg: ImageConfig) -> None:
    archive = download(D2CODING_URL, cfg.cache / f"D2Coding-Ver{D2CODING_VERSION}.zip")
    fonts = root / "usr/share/fonts/d2coding"
    licenses = root / "usr/share/licenses/d2coding"
    fonts.mkdir(parents=True, exist_ok=True)
    licenses.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            base = Path(name).name
            if base in D2CODING_FILES:
                (fonts / base).write_bytes(z.read(name))
            elif base == "OFL.txt":
                (licenses / "OFL.txt").write_bytes(z.read(name))
    (root / "etc/fonts/local.conf").write_text(_data("d2coding/local.conf"))
    profile = root / "etc/dconf/profile"
    profile.mkdir(parents=True, exist_ok=True)
    (profile / "user").write_text("user-db:user\nsystem-db:local\n")
    (profile / "gdm").write_text(
        "user-db:user\nsystem-db:gdm\nfile-db:/usr/share/gdm/greeter-dconf-defaults\n")
    for db in ("local", "gdm"):
        d = root / f"etc/dconf/db/{db}.d"
        d.mkdir(parents=True, exist_ok=True)
        (d / "00-fonts-d2coding").write_text(_data("d2coding/dconf-fonts"))
    in_chroot(root, "fc-cache -f >/dev/null && dconf update && fc-match sans-serif && fc-match monospace")


INSTALLERS = {"d2coding": install_d2coding}
