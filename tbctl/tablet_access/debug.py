# SPDX-License-Identifier: GPL-2.0-only
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
    remote = "/tmp/disp-regs.txt"
    with Session() as s:
        rc = run_script(s, "disp-regdump.sh", remote)
        if rc == 0:
            s.get(remote, output)
            print(f"-> {output}")
    return rc


def memory(action: str, appid: str, interval: float, output: Path) -> int:
    with Session() as s:
        s.put(_script("memtrack.py"), "/var/tmp/memtrack.py")
        cmd = ["python3", "/var/tmp/memtrack.py", action]
        rc = s.run(" ".join(cmd + ([appid, str(interval)] if action == "start" else [])),
                   timeout=24 * 3600 if action == "watch" else 600)
        if action == "start" and rc == 0:
            print(f"sampling every {interval:g}s (AppId {appid}); run `tbctl debug mem stop` after playing")
        if action == "stop" and rc == 0:
            s.get("/var/tmp/memtrack.csv", output)
            print(f"-> {output}")
        return rc


def gpu_status() -> int:
    with Session() as s:
        return run_script(s, "gpu-check.sh")
