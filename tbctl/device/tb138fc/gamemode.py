# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import zipfile
from dataclasses import replace
from pathlib import Path

from tbctl.core.chroot import in_chroot
from tbctl.core.config import load
from tbctl.core.fetch import download
from tbctl.core.host import give_back
from tbctl.core.process import BuildError, log, run
from tbctl.device.tb138fc import DATA
from tbctl.distro.archlinux.config import ImageConfig

OVERLAY = DATA / "rootfs" / "gamemode"
EXECUTABLE_DIRS = ("usr/local/bin", "usr/local/lib/steamos")
PACKAGES = ("sddm", "lsof", "squashfuse", "erofs-utils", "fuse3")
BUILD_USER = "tbctl-build"

GAMESCOPE_PATCHES = DATA / "rootfs" / "build" / "gamescope-patches"
LOCAL_PACKAGES = {
    "gtk2": ("https://aur.archlinux.org/gtk2.git", "master", ()),
    "gamescope": ("https://gitlab.archlinux.org/archlinux/packaging/packages/gamescope.git",
                  "3.16.31-1", tuple(sorted(GAMESCOPE_PATCHES.glob("*.patch")))),
}

FEX_REV = "FEX-2610"
FEX_URL = "https://github.com/FEX-Emu/FEX"
FEX_BUILD_DEPS = ("cmake", "ninja", "clang", "llvm", "lld", "python", "python-setuptools", "git")
FEX_ROOTFS_URL = "https://rootfs.fex-emu.gg/Ubuntu_24_04/2026-08-11/Ubuntu_24_04.sqsh"

STEAM_CDN = "https://client-update.steamstatic.com/"
STEAM_MANIFEST = "steam_client_steamdeck_publicbeta_linuxarm64"
STEAM_DIR = ".local/share/Steam-arm64"
RUN_STEAM = """#!/bin/sh
cd "$(dirname "$(readlink -f "$0")")" || exit 1
while :; do
	./steamrtarm64/steam "$@"
	rc=$?
	[ "$rc" -eq 42 ] || exit "$rc"
done
"""


def _stage(user: str) -> Path:
    stage = load().work / "gamemode-layer"
    shutil.rmtree(stage, ignore_errors=True)
    shutil.copytree(OVERLAY, stage, symlinks=True)
    for path in stage.rglob("*"):
        rel = path.relative_to(stage).as_posix()
        exe = path.is_dir() or any(rel.startswith(d + "/") for d in EXECUTABLE_DIRS)
        path.chmod(0o755 if exe else 0o644)
    stage.chmod(0o755)
    conf = stage / "etc/sddm.conf.d/10-tb138fc-autologin.conf"
    conf.write_text(conf.read_text().replace("@USER@", user))
    (stage / "etc/sddm.conf.d/zz-steamos-autologin.conf").write_text(
        "[Autologin]\nSession=gamescope-session.desktop\n")
    return stage


def _prepare_gamescope(pkgbuild: Path, patches: tuple[Path, ...]) -> None:
    s = pkgbuild.read_text()
    s = s.replace("pkgrel=1\n", "pkgrel=1.1\n", 1)
    names = [p.name for p in patches]
    s = s.replace("  git+https://gitlab.freedesktop.org/wlroots/wlroots.git\n)",
                  "  git+https://gitlab.freedesktop.org/wlroots/wlroots.git\n"
                  + "".join(f"  {n}\n" for n in names) + ")", 1)
    apply = "".join(f"  git apply ../{n}\n" for n in names)
    s = s.replace("git -c protocol.file.allow=always submodule update\n}",
                  "git -c protocol.file.allow=always submodule update\n" + apply + "}", 1)
    m = re.search(r"b2sums=\((.*?)\)", s, re.S)
    s = s[:m.end() - 1] + "".join("\n        'SKIP'" for _ in names) + ")" + s[m.end():]
    pkgbuild.write_text(s)


PREPARE = {"gtk2": lambda pkgbuild, patches: None, "gamescope": _prepare_gamescope}


def _local_packages(root: Path) -> None:
    cache = load().work / "pkgcache"
    cache.mkdir(parents=True, exist_ok=True)
    incoming = root / "tmp/localpkgs"
    incoming.mkdir(parents=True, exist_ok=True)
    for name, (repo, ref, patches) in LOCAL_PACKAGES.items():
        cached = sorted(cache.glob(f"{name}-[0-9]*-aarch64.pkg.tar.*"))
        if not cached:
            cached = [_build_package(root, name, repo, ref, patches, cache)]
        log(f"{name}: {cached[-1].name}")
        shutil.copy(cached[-1], incoming)
    in_chroot(root, "pacman -U --noconfirm --needed /tmp/localpkgs/*.pkg.tar.*\n"
                    "rm -rf /tmp/localpkgs\n"
                    "sed -i 's/^#\\?IgnorePkg *=.*/IgnorePkg   = gamescope/' /etc/pacman.conf")
    give_back(cache)


def _build_package(root: Path, name: str, repo: str, ref: str, patches: tuple[Path, ...],
                   cache: Path) -> Path:
    log(f"building {name} (makepkg in the image; cached afterwards)")
    work = f"/tmp/pkgbuild/{name}"
    in_chroot(root, f"""
pacman -S --noconfirm --needed base-devel git
id {BUILD_USER} >/dev/null 2>&1 || useradd -m {BUILD_USER}
rm -rf {work} && mkdir -p /tmp/pkgbuild && chown {BUILD_USER}: /tmp/pkgbuild
runuser -u {BUILD_USER} -- git clone -q --depth 1 --branch {ref} {repo} {work}
""")
    for patch in patches:
        shutil.copy(patch, root / work.lstrip("/"))
    PREPARE[name](root / work.lstrip("/") / "PKGBUILD", patches)
    in_chroot(root, f"""
cd {work}
chown -R {BUILD_USER}: .
pacman -Qq | sort > /tmp/pkgbuild/before
deps=$(bash -c 'source PKGBUILD; echo "${{depends[@]}} ${{makedepends[@]}}"')
pacman -S --noconfirm --needed $deps
runuser -u {BUILD_USER} -- env MAKEFLAGS=-j$(nproc) makepkg --ignorearch --nocheck --skipinteg --skippgpcheck --noconfirm
make_only=$(bash -c 'source PKGBUILD; echo "${{makedepends[@]}}"')
for p in $make_only; do grep -qx "$p" /tmp/pkgbuild/before || pacman -Rns --noconfirm "$p" || true; done
""")
    built = sorted((root / work.lstrip("/")).glob(f"{name}-[0-9]*-aarch64.pkg.tar.*"))
    if not built:
        raise BuildError(f"makepkg produced no {name} package")
    shutil.copy(built[-1], cache)
    in_chroot(root, f"rm -rf {work}")
    return cache / built[-1].name


def _fex(user: str):
    def hook(root: Path) -> None:
        cfg = load()
        cache = cfg.work / "pkgcache" / f"fex-{FEX_REV}-aarch64.tar.gz"
        if not cache.is_file():
            log(f"building {FEX_REV} (in the image; cached afterwards)")
            in_chroot(root, f"""
pacman -Qq | sort > /tmp/fex-before
pacman -S --noconfirm --needed {" ".join(FEX_BUILD_DEPS)}
rm -rf /tmp/fex && git clone -q --depth 1 --branch {FEX_REV} --recurse-submodules --shallow-submodules {FEX_URL} /tmp/fex
cd /tmp/fex
CC=clang CXX=clang++ cmake -S . -B build -G Ninja -D CMAKE_INSTALL_PREFIX=/usr/local \\
  -D CMAKE_BUILD_TYPE=Release -D ENABLE_LTO=False -D BUILD_FEXCONFIG=False \\
  -D BUILD_TESTING=False -D USE_LINKER=lld -D ENABLE_CCACHE=False >/dev/null
ninja -C build -j$(nproc) >/dev/null
DESTDIR=/tmp/fexroot ninja -C build install >/dev/null
tar -C /tmp/fexroot -czf /tmp/fex.tar.gz .
for p in {" ".join(FEX_BUILD_DEPS)}; do grep -qx "$p" /tmp/fex-before || pacman -Rns --noconfirm "$p" || true; done
rm -rf /tmp/fex /tmp/fexroot /tmp/fex-before
""")
            cache.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(root / "tmp/fex.tar.gz", cache)
            give_back(cache)
        run(["bsdtar", "-xpf", str(cache), "-C", str(root)])
        sqsh = download(FEX_ROOTFS_URL, cfg.work / "dl" / Path(FEX_ROOTFS_URL).name)
        home = root / "home" / user
        rootfs_dir = home / ".local/share/fex-emu/RootFS"
        rootfs_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(sqsh, rootfs_dir)
        conf = home / ".config/fex-emu"
        conf.mkdir(parents=True, exist_ok=True)
        (conf / "Config.json").write_text(f'{{"Config": {{"RootFS": "{sqsh.name}"}}}}\n')
        log(f"FEX {FEX_REV} + {sqsh.name}")
    return hook


def _steam(user: str):
    def hook(root: Path) -> None:
        cfg = load()
        dl = cfg.work / "dl" / "steam-arm64"
        manifest = (dl / STEAM_MANIFEST)
        manifest.unlink(missing_ok=True)
        download(STEAM_CDN + STEAM_MANIFEST, manifest)
        text = manifest.read_text()
        parts = []
        for block, body in re.findall(r'\n\t"([^"]+)"\n\t\{(.*?)\n\t\}', text, re.S):
            if not (block.endswith("_all") or block.endswith("_linuxarm64_linuxarm64")):
                continue
            file = re.search(r'"file"\s+"([^"]+)"', body).group(1)
            sha = re.search(r'"sha2"\s+"([^"]+)"', body).group(1)
            parts.append((file, sha))
        if not parts:
            raise BuildError(f"no client components in {STEAM_MANIFEST}")
        home = root / "home" / user
        steam = home / STEAM_DIR
        steam.mkdir(parents=True, exist_ok=True)
        for file, sha in parts:
            z = download(STEAM_CDN + file, dl / file)
            if hashlib.sha256(z.read_bytes()).hexdigest() != sha:
                z.unlink()
                raise BuildError(f"{file}: sha256 mismatch (deleted, run again)")
            with zipfile.ZipFile(z) as archive:
                for info in archive.infolist():
                    target = steam / info.filename.replace("\\", "/")
                    if info.is_dir() or info.filename.endswith(("/", "\\")):
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(info))
        for path in steam.rglob("*"):
            if path.is_file() and not path.is_symlink():
                with open(path, "rb") as f:
                    head = f.read(4)
                if head == b"\x7fELF" or head[:2] == b"#!":
                    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        version = re.search(r'"version"\s+"(\d+)"', text).group(1)
        (steam / "package-version").write_text(version + "\n")
        (steam / "run-steam").write_text(RUN_STEAM)
        (steam / "run-steam").chmod(0o755)
        os.symlink("steamrtarm64", steam / "steamrtarm32")
        dot = home / ".steam"
        dot.mkdir(exist_ok=True)
        base = f"/home/{user}/{STEAM_DIR}"
        for link, target in (("root", base), ("steam", base), ("bin64", f"{base}/steamrtarm64"),
                             ("binarm64", f"{base}/steamrtarm64"), ("sdk64", f"{base}/linuxarm64"),
                             ("sdkarm64", f"{base}/linuxarm64"), ("sdk32", f"{base}/linux32")):
            os.symlink(target, dot / link)
        log(f"Steam ARM64 client: {len(parts)} components in ~{user}/{STEAM_DIR}")
    return hook


def _finish(user: str):
    def hook(root: Path) -> None:
        in_chroot(root, f"""
systemctl --global enable tb138fc-gamescope-autologin.service
userdel -r {BUILD_USER} 2>/dev/null || true
rm -rf /tmp/pkgbuild
chown -R {user}: /home/{user}
""")
    return hook


def layer(image: ImageConfig) -> ImageConfig:
    user = image.account[0] if image.account else "alarm"
    return replace(
        image,
        packages=[*image.packages, *PACKAGES],
        overlays=[*image.overlays, _stage(user)],
        hooks=[*image.hooks, _local_packages, _fex(user), _steam(user), _finish(user)],
        display_manager="sddm",
    )
