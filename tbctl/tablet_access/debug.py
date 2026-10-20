# SPDX-License-Identifier: GPL-2.0-only
"""Debug helpers: run a packaged tablet-side script as root and collect its result."""
from __future__ import annotations

from importlib import resources
from pathlib import Path

from tbctl.tablet_access.ssh import Session


def _script(name: str) -> Path:
    return Path(str(resources.files(__package__).joinpath("scripts", name)))


def run_script(session: Session, name: str, *args: str) -> int:
    remote = f"/tmp/{name}"
    session.put(_script(name), remote)
    return session.run(" ".join(["sh", remote, *args]), root=True)


def display_registers(output: Path) -> int:
    """Dump the display-path registers (DPU, DSI, DSI PHY/PLL) into a local file."""
    remote = "/tmp/disp-regs.txt"
    with Session() as s:
        rc = run_script(s, "disp-regdump.sh", remote)
        if rc == 0:
            s.get(remote, output)
            print(f"-> {output}")
    return rc


def gpu_status() -> int:
    """Is GNOME rendering on the Adreno GPU?"""
    with Session() as s:
        return run_script(s, "gpu-check.sh")
