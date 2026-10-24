# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from pathlib import Path

from tbctl.core import host
from tbctl.core.config import load
from tbctl.core.process import BuildError, log, run
from tbctl.device.tb138fc import kernel

MKBOOTIMG_ARGS = [
    "--header_version", "2", "--os_version", "11.0.0", "--os_patch_level", "2021-10",
    "--pagesize", "4096", "--base", "0x0", "--kernel_offset", "0x8000",
    "--ramdisk_offset", "0x1000000", "--tags_offset", "0x100", "--dtb_offset", "0x1f00000",
]
CMDLINE = "console=tty0 clk_ignore_unused pd_ignore_unused rdinit=/init"

REQUIRED_TOOLS = ("mkbootimg",)


def build(tree: Path | None = None) -> Path:
    host.ensure(host.require_tools(list(REQUIRED_TOOLS)))
    tree = tree or kernel.tree_path()
    cfg = load()
    image = tree / "arch/arm64/boot/Image.gz"
    dtb = kernel.dtb_path(tree)
    ramdisk = cfg.out / "initramfs.cpio.gz"
    for f, how in ((image, "tbctl kernel build"), (dtb, "tbctl kernel build"),
                   (ramdisk, "tbctl initramfs")):
        if not f.is_file():
            raise BuildError(f"missing {f} (run `{how}`)")
    out = cfg.out / "boot.img"
    run(["mkbootimg", *MKBOOTIMG_ARGS, "--kernel", str(image), "--ramdisk", str(ramdisk),
         "--dtb", str(dtb), "--cmdline", CMDLINE, "-o", str(out)])
    log(f"{out} ({out.stat().st_size} bytes, kernel {kernel.kernelrelease(tree)})")
    return out
