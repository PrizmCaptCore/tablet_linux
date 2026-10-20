# SPDX-License-Identifier: GPL-2.0-only
"""Assemble the image: base tarball -> pacman (GNOME) -> system settings -> fonts -> layers.

Runs on Linux (WSL works) as root; packages are installed by the image's own pacman in a
chroot, so an x86 host needs qemu-user with binfmt_misc.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from tbctl.core import host
from tbctl.core.chroot import chroot_ready, in_chroot, loop_mounted
from tbctl.core.fetch import download, file_digest
from tbctl.core.process import BuildError, log, run, run_quiet
from tbctl.distro.archlinux import fonts
from tbctl.distro.archlinux.config import (ALARM_URL, BASE_PACKAGES, BASE_SERVICES,
                                           GNOME_EXCLUDE, ImageConfig)
from tbctl.distro.archlinux.pacman import relaxed_pacman


REQUIRED_TOOLS = ("mkfs.ext4", "e2fsck", "bsdtar", "mount", "umount", "chroot", "unshare",
                  "truncate", "img2simg")


def check(cfg: ImageConfig) -> None:
    tools = [t for t in REQUIRED_TOOLS if cfg.sparse or t != "img2simg"]
    problems = host.require_linux_root() + host.require_tools(tools) + host.require_aarch64_exec()
    unknown = [f for f in cfg.fonts if f not in fonts.INSTALLERS]
    if unknown:
        problems.append("unknown font option(s): " + ", ".join(unknown))
    host.ensure(problems)


def fetch_base(cache: Path) -> Path:
    tarball = download(ALARM_URL, cache / "ArchLinuxARM-aarch64-latest.tar.gz")
    md5 = download(ALARM_URL + ".md5", cache / "ArchLinuxARM-aarch64-latest.tar.gz.md5")
    expected = md5.read_text().split()[0]
    if file_digest(tarball, "md5") != expected:
        # a stale cached tarball against a newer .md5 (or a corrupt download): refetch both
        tarball.unlink()
        md5.unlink()
        raise BuildError("base tarball md5 mismatch (cache cleared, run again)")
    log(f"base tarball md5 ok ({expected})")
    return tarball


def create_image(cfg: ImageConfig) -> None:
    cfg.output.parent.mkdir(parents=True, exist_ok=True)
    cfg.output.unlink(missing_ok=True)
    run(["truncate", "-s", cfg.size, str(cfg.output)])
    run(["mkfs.ext4", "-q", "-L", cfg.label, str(cfg.output)])


def install_system(root: Path, cfg: ImageConfig) -> None:
    locales = list(dict.fromkeys([cfg.locale, "en_US.UTF-8"]))
    escaped = [l.replace(".", r"\.") for l in locales]
    locale_sed = "; ".join(rf"s/^#\({l}\)/\1/" for l in escaped)
    exclude = " ".join(f"-e {p}" for p in GNOME_EXCLUDE)
    drop_kernel = "pacman -Rns --noconfirm linux-aarch64 || true" if cfg.drop_kernel else ":"
    in_chroot(root, f"""
pacman-key --init
pacman-key --populate archlinuxarm
{drop_kernel}
pacman -Syu --noconfirm
pacman -S --noconfirm --needed $(pacman -Sgq gnome | grep -v -x {exclude}) {" ".join([*BASE_PACKAGES, *cfg.packages])}
systemctl enable {" ".join([*BASE_SERVICES, *cfg.services])}
echo {cfg.hostname} > /etc/hostname
echo 'LANG={cfg.locale}' > /etc/locale.conf
sed -i '{locale_sed}' /etc/locale.gen
locale-gen
ln -sf /usr/share/zoneinfo/{cfg.timezone} /etc/localtime
echo '%wheel ALL=(ALL:ALL) ALL' > /etc/sudoers.d/wheel
usermod -aG wheel alarm
""")


def apply_layers(root: Path, cfg: ImageConfig) -> None:
    for tar in cfg.overlay_tars:
        run(["bsdtar", "-xpf", str(tar), "-C", str(root)])
    for tree in cfg.overlays:
        run(["cp", "-a", "--no-preserve=ownership", f"{tree}/.", str(root)])
    for script in cfg.chroot_scripts:
        target = root / "tmp" / script.name
        shutil.copy(script, target)
        in_chroot(root, f"sh /tmp/{script.name}")
        target.unlink(missing_ok=True)


def finalize(cfg: ImageConfig) -> None:
    run_quiet(["e2fsck", "-fy", str(cfg.output)])
    run(["e2fsck", "-fn", str(cfg.output)])
    if cfg.sparse:
        cfg.sparse.parent.mkdir(parents=True, exist_ok=True)
        run(["img2simg", str(cfg.output), str(cfg.sparse)])


def build(cfg: ImageConfig) -> None:
    check(cfg)
    host.enter_private_mount_namespace()
    tarball = fetch_base(cfg.cache)
    create_image(cfg)
    with tempfile.TemporaryDirectory(prefix="tbctl-") as tmp:
        with loop_mounted(cfg.output, Path(tmp)) as root:
            run(["bsdtar", "-xpf", str(tarball), "-C", str(root)])
            with chroot_ready(root), relaxed_pacman(root):
                install_system(root, cfg)
                for font in cfg.fonts:
                    fonts.INSTALLERS[font](root, cfg)
                apply_layers(root, cfg)
            run(["du", "-sh", str(root)])
    finalize(cfg)
    log(f"done: {cfg.output}" + (f" (sparse: {cfg.sparse})" if cfg.sparse else ""))
