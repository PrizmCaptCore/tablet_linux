# SPDX-License-Identifier: GPL-2.0-only
"""What goes into the image."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ALARM_URL = "http://os.archlinuxarm.org/os/ArchLinuxARM-aarch64-latest.tar.gz"

# gnome-books and gnome-boxes have unresolvable dependencies (libsoup) on Arch Linux ARM,
# and pacman's --ignore does not apply to group selection: install the members explicitly.
GNOME_EXCLUDE = ("gnome-books", "gnome-boxes")
BASE_PACKAGES = (
    "gdm", "networkmanager", "openssh", "sudo",
    "noto-fonts", "noto-fonts-cjk", "noto-fonts-emoji",
    "pipewire-jack", "alsa-utils", "bluez", "bluez-utils",
    "mesa", "e2fsprogs", "usbutils", "vim",
)
BASE_SERVICES = ("gdm", "NetworkManager", "sshd", "systemd-networkd", "bluetooth")


@dataclass
class ImageConfig:
    output: Path                      # raw ext4 image to create
    sparse: Path | None = None        # also write an Android sparse image (fastboot)
    size: str = "16G"
    label: str = "rootfs"
    cache: Path = Path.home() / ".cache" / "tbctl"   # downloads (base tarball, fonts)
    hostname: str = "alarm"
    locale: str = "en_US.UTF-8"       # LANG; en_US.UTF-8 is always generated as well
    timezone: str = "UTC"
    fonts: list[str] = field(default_factory=list)
    packages: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    drop_kernel: bool = False         # remove linux-aarch64 (the board ships its own kernel)
    overlays: list[Path] = field(default_factory=list)        # directory trees copied to /
    overlay_tars: list[Path] = field(default_factory=list)    # tarballs extracted to /
    chroot_scripts: list[Path] = field(default_factory=list)  # run inside, after overlays
