# SPDX-License-Identifier: GPL-2.0-only
"""The bootloader (fastboot) and moving the tablet between Linux and fastboot."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from tbctl.core.config import load
from tbctl.core.process import BuildError, log
from tbctl.tablet_access import rescue
from tbctl.tablet_access.ssh import Session, reachable

# Lenovo's abl boots slot a only (it marks the other slot unbootable); `fastboot boot` is
# removed, so a kernel is tested by flashing it.
BOOT_PARTITION = "boot_a"
ROOTFS_PARTITION = "userdata"


def fastboot(*args: str, timeout: float = 600) -> subprocess.CompletedProcess:
    try:
        return subprocess.run([load().fastboot, *args], capture_output=True, text=True,
                              timeout=timeout)
    except FileNotFoundError:
        raise BuildError(f"fastboot not found ({load().fastboot}); set [tablet] fastboot") from None
    except subprocess.TimeoutExpired:
        raise BuildError(f"fastboot {' '.join(args)}: timed out") from None


def in_fastboot() -> bool:
    try:
        return bool(fastboot("devices", timeout=5).stdout.strip())
    except BuildError:
        return False


def _wait(condition, timeout: float, what: str) -> float:
    start = time.monotonic()
    while not condition():
        if time.monotonic() - start > timeout:
            raise BuildError(f"no {what} after {timeout:.0f}s")
        time.sleep(2)
    return time.monotonic() - start


def wait_for_fastboot(timeout: float = 120) -> None:
    _wait(in_fastboot, timeout, "fastboot device")


def wait_for_linux(timeout: float = 120) -> float:
    host = load().tablet_host
    return _wait(lambda: reachable(host), timeout, f"ssh on {host}")


def reboot_linux(bootloader: bool = False) -> None:
    """Reboot the running tablet (Arch over ssh, else the rescue shell) and wait until it
    has gone down, so a later wait cannot see the old system still answering."""
    host = load().tablet_host
    target = "bootloader" if bootloader else ""
    try:
        with Session(timeout=10) as s:
            # the session drops while systemd shuts down; the reboot has started by then
            s.capture(f"systemctl reboot --reboot-argument={target}" if target
                      else "systemctl reboot", root=True, timeout=20)
    except (BuildError, OSError):
        rescue.run(f"sync; /bin/rebootmode {target}" if target else "sync; reboot -f", timeout=15)
    _wait(lambda: not reachable(host, timeout=1), 60, "shutdown")


def enter_fastboot() -> None:
    if in_fastboot():
        return
    log("rebooting the tablet into fastboot")
    reboot_linux(bootloader=True)
    wait_for_fastboot()
    time.sleep(3)   # abl accepts commands a moment after it enumerates


def flash(partition: str, image: Path) -> None:
    if not image.is_file():
        raise BuildError(f"no such image: {image}")
    log(f"flashing {image} -> {partition}")
    r = fastboot("flash", partition, str(image), timeout=3600)   # an 8 GB rootfs over USB 2
    if r.returncode != 0:
        raise BuildError(f"fastboot flash {partition} failed:\n{r.stderr.strip()}")


def reboot_from_fastboot() -> None:
    r = fastboot("reboot", timeout=30)
    if r.returncode != 0:
        raise BuildError(f"fastboot reboot failed:\n{r.stderr.strip()}")
