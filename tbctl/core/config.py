# SPDX-License-Identifier: GPL-2.0-only
"""Settings from <repo>/config.toml (see config.example.toml); every key has a default."""
from __future__ import annotations

import functools
import os
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[2]
CONFIG_FILE = REPO / "config.toml"


@dataclass(frozen=True)
class Config:
    # [build]: Linux-side paths; only meaningful where the build steps run (Linux / WSL)
    work: Path
    out: Path
    backup: Path
    stock_firmware: Path | None
    # [wsl]
    wsl_distro: str
    # [tablet]
    tablet_host: str
    tablet_user: str
    fastboot: str

    @property
    def tablet_password(self) -> str:
        return os.environ.get("TB_PASS", "alarm")


def build_user_home() -> Path:
    """Home of the user the build belongs to. Root runs (loop mounts) are started through
    sudo or `wsl -u root`, which pass the real home in SUDO_USER / TBCTL_HOME."""
    if os.environ.get("TBCTL_HOME"):
        return Path(os.environ["TBCTL_HOME"])
    if os.environ.get("SUDO_USER"):
        return Path("~" + os.environ["SUDO_USER"]).expanduser()
    return Path.home()


def _build_path(value: str) -> Path:
    if os.name == "nt":
        # Linux-side path seen from Windows: keep it as text, it is never opened here
        return PurePosixPath(value)  # type: ignore[return-value]
    if value.startswith("~"):
        return build_user_home() / value[1:].lstrip("/")
    p = Path(value)
    return p if p.is_absolute() else REPO / p


def _default_fastboot() -> str:
    if shutil.which("fastboot"):
        return "fastboot"
    sdk = Path(os.environ.get("LOCALAPPDATA", "")) / "Android/platform-tools/fastboot.exe"
    return str(sdk) if sdk.exists() else "fastboot"


@functools.cache
def load() -> Config:
    data = tomllib.loads(CONFIG_FILE.read_text(encoding="utf-8")) if CONFIG_FILE.exists() else {}
    build, wsl, tablet = data.get("build", {}), data.get("wsl", {}), data.get("tablet", {})
    out = Path(build.get("out", "out"))
    return Config(
        work=_build_path(build.get("work", "~/tb138fc")),
        out=out if out.is_absolute() else REPO / out,   # the same repo path on both sides
        backup=_build_path(build.get("backup", "backup")),
        stock_firmware=_build_path(build["stock_firmware"]) if build.get("stock_firmware") else None,
        wsl_distro=wsl.get("distro", ""),
        # TB_HOST: one-off override, e.g. the tablet's Wi-Fi address
        tablet_host=os.environ.get("TB_HOST") or tablet.get("host", "172.16.42.1"),
        tablet_user=tablet.get("user", "alarm"),
        fastboot=tablet.get("fastboot") or _default_fastboot(),
    )
