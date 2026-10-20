# SPDX-License-Identifier: GPL-2.0-only
"""Proprietary files from the stock ZUI 14 QFIL package (`[build] stock_firmware`) and the
persist backup (`[build] backup`). Nothing produced here may be committed.

  extract():   NON-HLOS.bin, BTFM.bin and vendor (inside super) -> <work>/stock-fw
  stock_dt():  boot.img/dtbo.img DTBs -> <work>/stock (+ decompiled into docs/stock-dt)
  package():   remoteproc/GPU zap/amp firmware -> out/firmware-tb138fc.tar.gz
  hexagonfs(): hexagonrpcd's file tree (SLPI sensors) -> out/hexagonfs-tb138fc.tar.gz
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from tbctl.core import android, host
from tbctl.core.config import REPO, load
from tbctl.core.process import BuildError, log, run

# pil-squasher merges split .mdt/.bNN images into one .mbn, pinned to the revision used
PIL_SQUASHER_URL = "https://github.com/linux-msm/pil-squasher"
PIL_SQUASHER_REV = "3c9f8b8756ba6e4dbf9958570fd4c9aea7a70cf4"

SUPER_SIZE = 8 * 1024**3
FIRMWARE_DIR = "usr/lib/firmware/qcom/sm8250/LENOVO/TB138FC"
HEXAGONFS_DIR = "usr/share/qcom/sm8250/Lenovo/TB138FC"
REMOTEPROCS = ("adsp", "cdsp", "slpi", "venus")
VENDOR_DIRS = ("firmware", "firmware_mnt", "etc/wifi", "lib/firmware")
# stock DT: dtbo entry ovl04 is "kona MTP", board-id 0x10008 (this board)
STOCK_DT_DOCS = {"dtbs/base00.dts": "base-kona-v2.1.dts",
                 "dtbos/ovl04.dts": "overlay-kona-mtp-0x10008.dts"}

# Dynamic sensor modules (bring-to-ear, WiGig sensing; phone features): the SLPI stalls loading
# sns_bring_to_ear.so over FastRPC and its watchdog kills the sensor process 20 s later
# ("SEE Sensor exceeded processing time limit"), twice per boot. The SLPI re-parses the
# configs on every boot, so their configs and registry groups go as well.
SENSOR_DROP = {
    "sensors/config": ("kona_dynamic_sensors.json", "sns_bring_to_ear.json", "wigig_sensing_0.json"),
    "sensors/registry": ("sns_dynamic_sensors*", "sns_bring_to_ear*", "wigig_sensing*"),
    "dsp/sdsp": ("sns_bring_to_ear.so", "wigig_sensing.so"),
}
# /sys/devices/soc0 as Android reports it (hexagonrpcd answers the SLPI's socinfo queries)
SOCINFO = {"hw_platform": "MTP", "platform_subtype": "Unknown", "platform_subtype_id": "0",
           "platform_version": "65536", "revision": "2.1", "soc_id": "356"}

REQUIRED_TOOLS = ("mcopy", "unpack_bootimg", "dtc", "fsck.erofs", "debugfs", "git", "make",
                  "cc", "tar")


def _images() -> Path:
    images = load().stock_firmware
    if images is None or not (images / "rawprogram_unsparse0.xml").is_file():
        raise BuildError("set [build] stock_firmware in config.toml to the extracted ZUI "
                         "QFIL package's image/ directory")
    return images


def stock_fw() -> Path:
    return load().work / "stock-fw"


def _tar(src: Path, out: Path, *members: str) -> None:
    """A reproducible tarball: sorted, root-owned, fixed timestamps."""
    out.parent.mkdir(parents=True, exist_ok=True)
    run(["tar", "-C", str(src), "--sort=name", "--owner=0", "--group=0", "--numeric-owner",
         "--mtime=2021-01-01 00:00:00 UTC", "--mode=u=rwX,go=rX", "-I", "gzip -9n",
         "-cf", str(out), *members])


def _debugfs_rdump(image: Path, path: str, dest: Path) -> None:
    run(["debugfs", "-R", f"rdump {path} {dest}", str(image)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------------------------------------------------------------------------- extraction

def extract() -> Path:
    host.ensure(host.require_tools(list(REQUIRED_TOOLS)))
    images = _images()
    fw = stock_fw()
    shutil.rmtree(fw, ignore_errors=True)
    for d in ("modem", "bt", "vendor", "tmp"):
        (fw / d).mkdir(parents=True)
    # FAT images: remoteproc firmware (.mdt/.bNN) and QCA6390 Bluetooth firmware
    run(["mcopy", "-s", "-n", "-i", str(images / "NON-HLOS.bin"), "::/", f"{fw / 'modem'}/"])
    run(["mcopy", "-s", "-n", "-i", str(images / "BTFM.bin"), "::/", f"{fw / 'bt'}/"])

    super_img = fw / "tmp/super.img"
    log(f"super: {android.assemble_qfil_chunks(images, 'super', super_img, SUPER_SIZE)} chunks")
    vendor_img = fw / "tmp/vendor.img"
    name = android.extract_logical_partition(super_img, ["vendor_a", "vendor"], vendor_img)
    super_img.unlink()
    root = fw / "tmp/vendor-root"
    if run(["dump.erofs", str(vendor_img)], check=False, capture_output=True).returncode == 0:
        run(["fsck.erofs", f"--extract={root}", str(vendor_img)], stdout=subprocess.DEVNULL)
    else:
        root.mkdir()
        _debugfs_rdump(vendor_img, "/", root)
    for d in VENDOR_DIRS:
        if (root / d).is_dir():
            shutil.copytree(root / d, fw / "vendor" / d, symlinks=True)
    log(f"{fw}: modem, bt, vendor (from {name})")
    return fw


def stock_dt() -> Path:
    """Split the stock DTBs (base SoC trees from boot.img, board overlays from dtbo.img) into
    <work>/stock/{dtbs,dtbos}, decompile them, and refresh the two kept in docs/stock-dt."""
    host.ensure(host.require_tools(["unpack_bootimg", "dtc"]))
    images = _images()
    stock = load().work / "stock"
    shutil.rmtree(stock, ignore_errors=True)
    run(["unpack_bootimg", "--boot_img", str(images / "boot.img"), "--out", str(stock / "boot")],
        stdout=subprocess.DEVNULL)
    sets = {"dtbs": ("base", (stock / "boot/dtb").read_bytes(), 0),
            "dtbos": ("ovl", (images / "dtbo.img").read_bytes(), 4)}
    for sub, (prefix, blob, skip) in sets.items():
        (stock / sub).mkdir(parents=True)
        for n, dtb in enumerate(android.split_dtbs(blob, skip)):
            path = stock / sub / f"{prefix}{n:02d}.dtb"
            path.write_bytes(dtb)
            run(["dtc", "-I", "dtb", "-O", "dts", "-q", "-o", str(path.with_suffix(".dts")),
                 str(path)], stdin=subprocess.DEVNULL)
    docs = REPO / "docs/stock-dt"
    docs.mkdir(exist_ok=True)
    for src, dst in STOCK_DT_DOCS.items():
        shutil.copy(stock / src, docs / dst)
    return stock


# ---------------------------------------------------------------------------- packaging

def _pil_squasher() -> Path:
    src = load().work / "pil-squasher"
    tool = src / "pil-squasher"
    if not (src / ".git").exists():
        src.mkdir(parents=True, exist_ok=True)
        run(["git", "-C", str(src), "init", "-q"])
        run(["git", "-C", str(src), "remote", "add", "origin", PIL_SQUASHER_URL])
    head = run(["git", "-C", str(src), "rev-parse", "HEAD"], check=False, capture_output=True,
               text=True).stdout.strip()
    if head != PIL_SQUASHER_REV or not tool.exists():
        run(["git", "-C", str(src), "fetch", "-q", "--depth", "1", "origin", PIL_SQUASHER_REV])
        run(["git", "-C", str(src), "checkout", "-q", "--force", PIL_SQUASHER_REV])
        run(["make", "-s", "-C", str(src), "clean"], check=False, capture_output=True)
        run(["make", "-s", "-C", str(src)])
    return tool


def package() -> Path:
    fw = stock_fw()
    if not (fw / "modem/image").is_dir():
        raise BuildError(f"{fw} not extracted (run `tbctl firmware extract`)")
    squash = _pil_squasher()
    stage = load().work / "firmware-stage"
    shutil.rmtree(stage, ignore_errors=True)
    dest = stage / FIRMWARE_DIR
    dest.mkdir(parents=True)
    for name in REMOTEPROCS:
        run([str(squash), str(dest / f"{name}.mbn"), str(fw / f"modem/image/{name}.mdt")])
    run([str(squash), str(dest / "a650_zap.mbn"), str(fw / "vendor/firmware/a650_zap.mdt")])
    # Cirrus CS35L43 speaker amp DSP firmware and tunings
    cirrus = stage / "usr/lib/firmware/cirrus"
    cirrus.mkdir(parents=True)
    amp = sorted((fw / "vendor/firmware").glob("spk*-cs35l43-*"))
    if not amp:
        raise BuildError("no spk*-cs35l43-* files in the vendor firmware")
    for f in amp:
        shutil.copy(f, cirrus)
    out = load().out / "firmware-tb138fc.tar.gz"
    _tar(stage, out, "usr")
    log(f"{out}: {len(REMOTEPROCS) + 1} remoteproc/zap images, {len(amp)} amp files")
    return out


def hexagonfs() -> Path:
    """hexagonrpcd's file tree (see hexagonrpcd(1)):
      acdb                 <- /vendor/etc/acdbdata
      dsp                  <- dsp partition (dspso.bin)
      sensors/config       <- /vendor/etc/sensors/config
      sensors/registry     <- persist /sensors/registry/registry
      sensors/sns_reg_version <- persist (seeds the writable registry, rootfs/install-hexagonrpcd.sh)
      sensors/sns_reg.conf <- /vendor/etc/sensors/sns_reg_config
      socinfo              <- Android's /sys/devices/soc0 values
    """
    host.ensure(host.require_tools(["debugfs", "tar"]))
    cfg = load()
    images = _images()
    vendor = stock_fw() / "tmp/vendor-root"
    if not (vendor / "etc/sensors").is_dir():
        raise BuildError(f"{vendor} not extracted (run `tbctl firmware extract`)")
    persist = cfg.backup / "persist.img"
    if not persist.is_file():
        raise BuildError(f"{persist} missing: [build] backup must hold the persist EDL dump")
    stage = cfg.work / "hexagonfs-root"
    shutil.rmtree(stage, ignore_errors=True)
    d = stage / HEXAGONFS_DIR
    for sub in ("dsp", "sensors/config", "socinfo", "acdb"):
        (d / sub).mkdir(parents=True)

    _debugfs_rdump(images / "dspso.bin", "/", d / "dsp")
    shutil.rmtree(d / "dsp/lost+found", ignore_errors=True)
    shutil.copytree(vendor / "etc/sensors/config", d / "sensors/config", dirs_exist_ok=True)
    shutil.copy(vendor / "etc/sensors/sns_reg_config", d / "sensors/sns_reg.conf")
    _debugfs_rdump(persist, "/sensors/registry/registry", d / "sensors")
    run(["debugfs", "-R", f"dump /sensors/registry/sns_reg_version {d / 'sensors/sns_reg_version'}",
         str(persist)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if (vendor / "etc/acdbdata").is_dir():
        shutil.copytree(vendor / "etc/acdbdata", d / "acdb", dirs_exist_ok=True)

    for sub, patterns in SENSOR_DROP.items():
        for pattern in patterns:
            for f in (d / sub).glob(pattern):
                if f.is_file():
                    f.unlink()
    for name, value in SOCINFO.items():
        (d / "socinfo" / name).write_text(value + "\n")

    count = lambda p: sum(1 for f in p.rglob("*") if f.is_file())  # noqa: E731
    log(f"dsp: {count(d / 'dsp')} files, sensors/config: {count(d / 'sensors/config')}, "
        f"registry: {count(d / 'sensors/registry')}, acdb: {count(d / 'acdb')}")
    out = cfg.out / "hexagonfs-tb138fc.tar.gz"
    _tar(stage, out, "usr")
    return out
