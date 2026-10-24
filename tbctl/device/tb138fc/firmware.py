# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from tbctl.core import android, host
from tbctl.core.config import load
from tbctl.core.process import BuildError, log, run

PIL_SQUASHER_URL = "https://github.com/linux-msm/pil-squasher"
PIL_SQUASHER_REV = "3c9f8b8756ba6e4dbf9958570fd4c9aea7a70cf4"

SUPER_SIZE = 8 * 1024**3
FIRMWARE_DIR = "usr/lib/firmware/qcom/sm8250/LENOVO/TB138FC"
HEXAGONFS_DIR = "usr/share/qcom/sm8250/Lenovo/TB138FC"
REMOTEPROCS = ("adsp", "cdsp", "slpi", "venus")
VENDOR_DIRS = ("firmware", "firmware_mnt", "etc/wifi", "lib/firmware")

SENSOR_DROP = {
    "sensors/config": ("kona_dynamic_sensors.json", "sns_bring_to_ear.json", "wigig_sensing_0.json"),
    "sensors/registry": ("sns_dynamic_sensors*", "sns_bring_to_ear*", "wigig_sensing*"),
    "dsp/sdsp": ("sns_bring_to_ear.so", "wigig_sensing.so"),
}
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
    out.parent.mkdir(parents=True, exist_ok=True)
    run(["tar", "-C", str(src), "--sort=name", "--owner=0", "--group=0", "--numeric-owner",
         "--mtime=2021-01-01 00:00:00 UTC", "--mode=u=rwX,go=rX", "-I", "gzip -9n",
         "-cf", str(out), *members])


def _debugfs_rdump(image: Path, path: str, dest: Path) -> None:
    run(["debugfs", "-R", f"rdump {path} {dest}", str(image)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def extract() -> Path:
    host.ensure(host.require_tools(list(REQUIRED_TOOLS)))
    images = _images()
    fw = stock_fw()
    shutil.rmtree(fw, ignore_errors=True)
    for d in ("modem", "bt", "vendor", "tmp"):
        (fw / d).mkdir(parents=True)
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
    return stock


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

    count = lambda p: sum(1 for f in p.rglob("*") if f.is_file())
    log(f"dsp: {count(d / 'dsp')} files, sensors/config: {count(d / 'sensors/config')}, "
        f"registry: {count(d / 'sensors/registry')}, acdb: {count(d / 'acdb')}")
    out = cfg.out / "hexagonfs-tb138fc.tar.gz"
    _tar(stage, out, "usr")
    return out
