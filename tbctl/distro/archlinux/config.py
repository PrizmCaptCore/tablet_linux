# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

ALARM_URL = "http://os.archlinuxarm.org/os/ArchLinuxARM-aarch64-latest.tar.gz"

GNOME_EXCLUDE = ("gnome-books", "gnome-boxes")
BASE_PACKAGES = (
    "gdm", "networkmanager", "openssh", "sudo",
    "noto-fonts", "noto-fonts-cjk", "noto-fonts-emoji",
    "pipewire-jack", "alsa-utils", "bluez", "bluez-utils",
    "mesa", "e2fsprogs", "usbutils", "vim",
)
BASE_SERVICES = ("NetworkManager", "sshd", "systemd-networkd", "bluetooth")


@dataclass
class ImageConfig:
    output: Path
    sparse: Path | None = None
    size: str = "16G"
    label: str = "rootfs"
    cache: Path = Path.home() / ".cache" / "tbctl"
    hostname: str = "alarm"
    locale: str = "en_US.UTF-8"
    timezone: str = "UTC"
    fonts: list[str] = field(default_factory=list)
    packages: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    drop_kernel: bool = False
    overlays: list[Path] = field(default_factory=list)
    overlay_tars: list[Path] = field(default_factory=list)
    chroot_scripts: list[Path] = field(default_factory=list)
    hooks: list[Callable[[Path], None]] = field(default_factory=list)
    account: tuple[str, str] | None = None
    display_manager: str = "gdm"
