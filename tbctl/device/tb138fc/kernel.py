# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

from tbctl.core import host
from tbctl.core.config import load
from tbctl.device.tb138fc import DATA
from tbctl.core.fetch import download, file_digest
from tbctl.core.process import BuildError, log, run, run_filtered

KERNEL_VERSION = "7.2.11"
_MAJOR = KERNEL_VERSION.split(".")[0]
KERNEL_URL = f"https://cdn.kernel.org/pub/linux/kernel/v{_MAJOR}.x/linux-{KERNEL_VERSION}.tar.xz"
KERNEL_SUMS_URL = f"https://cdn.kernel.org/pub/linux/kernel/v{_MAJOR}.x/sha256sums.asc"

DTS_NAME = "sm8250-lenovo-tb138fc"
PATCH_DIR = DATA / "kernel" / "patches"
CONFIG_FRAGMENT = DATA / "kernel" / "tb138fc.config"
APPLIED_RECORD = ".tb138fc-patches"

MAKE_ENV = {"ARCH": "arm64", "CROSS_COMPILE": "aarch64-linux-gnu-"}
REQUIRED_TOOLS = ("make", "gcc", "aarch64-linux-gnu-gcc", "aarch64-linux-gnu-strip", "bc",
                  "bison", "flex", "patch", "tar", "xz")
NOISE = re.compile(r"Warning \(|^\s*$")


def tree_path() -> Path:
    return load().work / "linux"


def _make(tree: Path, *targets: str, **kw):
    env = dict(os.environ, **MAKE_ENV)
    return run(["make", "-s", "-C", str(tree), *targets], env=env, **kw)


def kernelrelease(tree: Path) -> str:
    return _make(tree, "kernelrelease", capture_output=True, text=True).stdout.strip()


def fetch_tree(tree: Path) -> None:
    if tree.exists():
        return
    dl = load().work / "dl"
    tarball = download(KERNEL_URL, dl / f"linux-{KERNEL_VERSION}.tar.xz")
    sums = download(KERNEL_SUMS_URL, dl / f"linux-v{_MAJOR}.x-sha256sums.asc")
    expected = next((l.split()[0] for l in sums.read_text().splitlines()
                     if l.endswith(f" linux-{KERNEL_VERSION}.tar.xz")), None)
    if expected is None:
        sums.unlink()
        raise BuildError(f"linux-{KERNEL_VERSION}.tar.xz not in sha256sums.asc (run again)")
    if file_digest(tarball, "sha256") != expected:
        tarball.unlink()
        raise BuildError("kernel tarball sha256 mismatch (deleted, run again)")
    tmp = Path(tempfile.mkdtemp(prefix="linux-", dir=tree.parent))
    run(["tar", "-xf", str(tarball), "-C", str(tmp), "--strip-components=1"])
    tmp.rename(tree)


def apply_patches(tree: Path) -> list[str]:
    record = tree / APPLIED_RECORD
    applied = set(record.read_text().split()) if record.exists() else set()
    new = []
    for patch in sorted(PATCH_DIR.glob("*.patch")):
        if patch.name in applied:
            continue
        r = run(["patch", "-p1", "-s", "--no-backup-if-mismatch", "-d", str(tree),
                 "-i", str(patch)], check=False)
        if r.returncode != 0:
            raise BuildError(f"{patch.name} does not apply (tree: {tree})")
        with open(record, "a") as f:
            f.write(patch.name + "\n")
        new.append(patch.name)
        log(f"applied {patch.name}")
    return new


def patch_status(tree: Path) -> list[tuple[str, str]]:
    record = tree / APPLIED_RECORD
    applied = set(record.read_text().split()) if record.exists() else set()
    status = []
    for patch in sorted(PATCH_DIR.glob("*.patch")):
        def dry(*flags: str) -> bool:
            return run(["patch", "-p1", "--dry-run", "-s", "-f", *flags, "-d", str(tree),
                        "-i", str(patch)], check=False, capture_output=True).returncode == 0
        state = ("recorded" if patch.name in applied else
                 "applies" if dry() else "already-in" if dry("-R") else "conflicts")
        status.append((patch.name, state))
    return status


def _insert_once(path: Path, marker: str, text: str, before: str | None = None) -> None:
    s = path.read_text()
    if marker in s:
        return
    if before is None:
        s = s + text
    else:
        if before + "\n" not in s:
            raise BuildError(f"{path}: anchor '{before}' not found (kernel layout changed)")
        s = s.replace(before + "\n", text + before + "\n", 1)
    path.write_text(s)


def install_out_of_tree(tree: Path) -> None:
    qcom = tree / "arch/arm64/boot/dts/qcom"
    shutil.copy(DATA / "dts" / f"{DTS_NAME}.dts", qcom)
    _insert_once(qcom / "Makefile", f"{DTS_NAME}.dtb",
                 f"dtb-$(CONFIG_ARCH_QCOM)\t+= {DTS_NAME}.dtb\n",
                 before=None)

    panel = tree / "drivers/gpu/drm/panel"
    shutil.copy(DATA / "kernel/panel/panel-raydium-rm692h0.c", panel)
    (panel / "Kconfig.tb138fc").write_text(
        "config DRM_PANEL_RAYDIUM_RM692H0\n"
        '\ttristate "Raydium RM692H0 dual-DSI panel (Lenovo TB138FC)"\n'
        "\tdepends on OF && DRM_MIPI_DSI && BACKLIGHT_CLASS_DEVICE\n"
        "\tselect DRM_DISPLAY_DSC_HELPER\n"
        "\tselect DRM_DISPLAY_HELPER\n")
    _insert_once(panel / "Kconfig", "Kconfig.tb138fc",
                 'source "drivers/gpu/drm/panel/Kconfig.tb138fc"\n\n',
                 before="config DRM_PANEL_RAYDIUM_RM69380")
    _insert_once(panel / "Makefile", "panel-raydium-rm692h0.o",
                 "obj-$(CONFIG_DRM_PANEL_RAYDIUM_RM692H0) += panel-raydium-rm692h0.o\n")

    codecs = tree / "sound/soc/codecs"
    for name in ("cs35l43.c", "cs35l43.h", "cs35l43-i2c.c", "cs35l43-tables.c"):
        shutil.copy(DATA / "kernel/cs35l43" / name, codecs)
    shutil.copy(DATA / "kernel/cs35l43/sound-cs35l43.h", tree / "include/sound/cs35l43.h")
    _insert_once(codecs / "Kconfig", "config SND_SOC_CS35L43\n",
                 "config SND_SOC_CS35L43\n\ttristate\n\tselect SND_SOC_WM_ADSP\n\n"
                 "config SND_SOC_CS35L43_I2C\n\ttristate \"Cirrus Logic CS35L43 CODEC (I2C)\"\n"
                 "\tdepends on I2C\n\tselect REGMAP_I2C\n\tselect SND_SOC_CS35L43\n\n",
                 before="config SND_SOC_CS35L45")
    _insert_once(codecs / "Makefile", "snd-soc-cs35l43-i2c",
                 "snd-soc-cs35l43-i2c-y := cs35l43-i2c.o cs35l43.o cs35l43-tables.o\n"
                 "obj-$(CONFIG_SND_SOC_CS35L43_I2C)\t+= snd-soc-cs35l43-i2c.o\n")


def _parse_config(text: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        if m := re.match(r"(CONFIG_\w+)=(.*)$", line):
            values[m[1]] = m[2]
        elif m := re.match(r"# (CONFIG_\w+) is not set$", line):
            values[m[1]] = "n"
    return values


def configure(tree: Path) -> None:
    _make(tree, "defconfig")
    env = dict(os.environ, **MAKE_ENV)
    run([str(tree / "scripts/kconfig/merge_config.sh"), "-m", "-O", str(tree),
         str(tree / ".config"), str(CONFIG_FRAGMENT)], cwd=tree, env=env,
        capture_output=True)
    _make(tree, "olddefconfig")
    wanted = _parse_config(CONFIG_FRAGMENT.read_text())
    final = _parse_config((tree / ".config").read_text())
    dropped = [f"{k}: wanted {v}, got {final.get(k, 'absent')}"
               for k, v in wanted.items() if final.get(k, "n") != v]
    if dropped:
        raise BuildError("config values did not survive olddefconfig:\n  " + "\n  ".join(dropped))


def config_values(tree: Path, symbols: list[str]) -> list[str]:
    final = _parse_config((tree / ".config").read_text())
    return [f"CONFIG_{s.removeprefix('CONFIG_')}="
            f"{final.get('CONFIG_' + s.removeprefix('CONFIG_'), '(absent)')}" for s in symbols]


def build(tree: Path | None = None) -> Path:
    tree = tree or tree_path()
    host.ensure(host.require_tools(list(REQUIRED_TOOLS)))
    tree.parent.mkdir(parents=True, exist_ok=True)
    fetch_tree(tree)
    apply_patches(tree)
    install_out_of_tree(tree)
    configure(tree)
    env = dict(os.environ, **MAKE_ENV)
    run_filtered(["make", "-s", "-C", str(tree), f"-j{os.cpu_count()}",
                  "Image.gz", "dtbs", "modules"], drop=NOISE, env=env)
    log(f"kernel {kernelrelease(tree)}: {tree / 'arch/arm64/boot/Image.gz'}, "
        f"{dtb_path(tree)}")
    return tree


def dtb_path(tree: Path) -> Path:
    return tree / f"arch/arm64/boot/dts/qcom/{DTS_NAME}.dtb"


def modules_tarball(tree: Path | None = None) -> Path:
    tree = tree or tree_path()
    cfg = load()
    kver = kernelrelease(tree)
    stage = cfg.work / "modstage"
    shutil.rmtree(stage, ignore_errors=True)
    _make(tree, f"INSTALL_MOD_PATH={stage / 'usr'}", "INSTALL_MOD_STRIP=1", "modules_install")
    (stage / f"usr/lib/modules/{kver}/build").unlink(missing_ok=True)
    out = cfg.out / f"modules-{kver}.tar.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
    run(["tar", "-C", str(stage), "--owner=0", "--group=0", "-czf", str(out), "usr"])
    return out
