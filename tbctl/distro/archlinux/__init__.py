# SPDX-License-Identifier: GPL-2.0-only
"""Arch Linux ARM (aarch64) + GNOME root filesystem image.

Device-neutral: device support (kernel modules, firmware, services) is added through the
generic overlay / overlay-tar / chroot-script hooks of ImageConfig.
"""
from tbctl.distro.archlinux.build import build
from tbctl.distro.archlinux.config import ImageConfig
from tbctl.distro.archlinux.inspect import inspect

__all__ = ["ImageConfig", "build", "inspect"]
