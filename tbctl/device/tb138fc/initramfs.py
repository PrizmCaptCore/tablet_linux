# SPDX-License-Identifier: GPL-2.0-only
"""The initramfs: Alpine minirootfs (busybox) + busybox-extras (telnetd, udhcpd) + small static
helpers (initramfs/src) + initramfs/init. It mounts the Arch root or stays in a rescue shell.

The archive is reproducible: pinned inputs, fixed timestamps, root ownership, sorted entries.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from tbctl.core import host
from tbctl.core.config import REPO, load
from tbctl.core.fetch import download, file_digest
from tbctl.core.process import BuildError, log, run

ALPINE_BRANCH = "v3.24"
ALPINE = f"https://dl-cdn.alpinelinux.org/alpine/{ALPINE_BRANCH}"
MINIROOTFS = "alpine-minirootfs-3.24.2-aarch64.tar.gz"
MINIROOTFS_URL = f"{ALPINE}/releases/aarch64/{MINIROOTFS}"
# Alpine drops superseded package builds from its mirrors: when this 404s, take the current
# busybox-extras version of the branch from https://pkgs.alpinelinux.org/packages
BUSYBOX_EXTRAS = "busybox-extras-1.37.0-r31.apk"
BUSYBOX_EXTRAS_URL = f"{ALPINE}/main/aarch64/{BUSYBOX_EXTRAS}"

HELPERS = ("rebootmode", "devmem")      # initramfs/src/<name>.c -> /bin/<name>
INIT = REPO / "initramfs" / "init"
MTIME = "2021-01-01 00:00:00 UTC"       # every entry gets this timestamp

REQUIRED_TOOLS = ("tar", "cpio", "gzip", "touch", "aarch64-linux-gnu-gcc")


def fetch_inputs(dl: Path) -> tuple[Path, Path]:
    rootfs = download(MINIROOTFS_URL, dl / MINIROOTFS)
    sums = download(MINIROOTFS_URL + ".sha256", dl / (MINIROOTFS + ".sha256"))
    if file_digest(rootfs, "sha256") != sums.read_text().split()[0]:
        rootfs.unlink()
        raise BuildError(f"{MINIROOTFS}: sha256 mismatch (deleted, run again)")
    try:
        extras = download(BUSYBOX_EXTRAS_URL, dl / BUSYBOX_EXTRAS)
    except BuildError:
        raise BuildError(f"{BUSYBOX_EXTRAS} is gone from the Alpine mirror; update "
                         "BUSYBOX_EXTRAS in tbctl/device/tb138fc/initramfs.py") from None
    return rootfs, extras


def build() -> Path:
    host.ensure(host.require_tools(list(REQUIRED_TOOLS)))
    cfg = load()
    rootfs, extras = fetch_inputs(cfg.work / "dl")
    stage = cfg.work / "initramfs"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    run(["tar", "-xzf", str(rootfs), "-C", str(stage)])
    # an .apk is concatenated gzip streams: signature, control (.PKGINFO), data
    run(["tar", "-xzf", str(extras), "-C", str(stage), "--exclude=.*"], check=False,
        stderr=subprocess.DEVNULL)   # tar complains about the trailing streams
    if not (stage / "usr/bin/busybox-extras").exists() and not (stage / "bin/busybox-extras").exists():
        raise BuildError(f"busybox-extras missing after unpacking {extras.name}")
    for name in HELPERS:
        run(["aarch64-linux-gnu-gcc", "-static", "-O2", "-o", str(stage / "bin" / name),
             str(REPO / "initramfs/src" / f"{name}.c")])
    shutil.copy(INIT, stage / "init")
    (stage / "init").chmod(0o755)

    run(["find", str(stage), "-exec", "touch", "-h", "-d", MTIME, "{}", "+"])
    out = cfg.out / "initramfs.cpio.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
    # sorted names, root:root, no inode numbers / timestamps beyond MTIME, no gzip name/time
    run(["sh", "-c", "find . -mindepth 1 | LC_ALL=C sort | "
         "cpio -o -H newc --quiet --reproducible -R 0:0 | gzip -9 -n > \"$0\"", str(out)],
        cwd=stage)
    log(f"{out} ({out.stat().st_size} bytes)")
    return out
