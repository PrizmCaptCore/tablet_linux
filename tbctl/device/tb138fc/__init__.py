# SPDX-License-Identifier: GPL-2.0-only
"""Lenovo Xiaoxin Pad Pro 2022 (TB138FC, SM8250).

Code here, data in data/ (paths in these modules' comments are relative to it).
"""

from pathlib import Path

# what the build steps read: dts/, kernel/, initramfs/, rootfs/
DATA = Path(__file__).resolve().parent / "data"
