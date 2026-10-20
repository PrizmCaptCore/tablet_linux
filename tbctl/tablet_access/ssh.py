# SPDX-License-Identifier: GPL-2.0-only
"""The tablet's Arch system over ssh/sftp (USB NCM 172.16.42.1, or its Wi-Fi address)."""
from __future__ import annotations

import os
import shlex
import socket
import subprocess
import sys
import time
from pathlib import Path

from tbctl.core.config import Config, load
from tbctl.core.process import BuildError


def reachable(host: str, port: int = 22, timeout: float = 2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class Session:
    """One ssh connection: `with Session() as s: s.run("uptime")`."""

    def __init__(self, cfg: Config | None = None, timeout: float = 15):
        self.cfg = cfg or load()
        self.timeout = timeout
        self.client = None

    def __enter__(self) -> "Session":
        import paramiko   # only the tablet commands need it

        self.client = paramiko.SSHClient()
        # the host key changes on every rootfs rebuild; this is a point-to-point USB link
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.client.connect(self.cfg.tablet_host, username=self.cfg.tablet_user,
                                password=self.cfg.tablet_password, timeout=self.timeout,
                                allow_agent=False, look_for_keys=False)
        except (OSError, paramiko.SSHException) as e:
            raise BuildError(f"ssh {self.cfg.tablet_user}@{self.cfg.tablet_host}: {e}") from None
        return self

    def __exit__(self, *exc) -> None:
        self.client.close()

    def _start(self, cmd: str, root: bool):
        chan = self.client.get_transport().open_session()
        if root:
            # sshd refuses root password logins: go through sudo, password on stdin (not
            # in the command line, where any process listing would show it)
            chan.exec_command(f"sudo -S -p '' sh -c {shlex.quote(cmd)}")
            chan.sendall((self.cfg.tablet_password + "\n").encode())
        else:
            chan.exec_command(cmd)
        return chan

    def run(self, cmd: str, root: bool = False, timeout: float = 600) -> int:
        """Run cmd, streaming its output; return its exit status."""
        chan = self._start(cmd, root)
        out = sys.stdout.buffer
        err = sys.stderr.buffer
        deadline = time.monotonic() + timeout
        while True:
            busy = False
            if chan.recv_ready():
                out.write(chan.recv(65536)); out.flush(); busy = True
            if chan.recv_stderr_ready():
                err.write(chan.recv_stderr(65536)); err.flush(); busy = True
            if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
                return chan.recv_exit_status()
            if time.monotonic() > deadline:
                chan.close()
                raise BuildError(f"timed out after {timeout:.0f}s: {cmd}")
            if not busy:
                time.sleep(0.05)

    def capture(self, cmd: str, root: bool = False, timeout: float = 600) -> tuple[int, str]:
        """Run cmd and return (exit status, stdout + stderr)."""
        chan = self._start(cmd, root)
        chan.settimeout(timeout)
        chan.set_combine_stderr(True)
        data = b""
        while chunk := chan.recv(65536):
            data += chunk
        return chan.recv_exit_status(), data.decode("utf-8", "replace")

    def put(self, local: Path, remote: str) -> None:
        with self.client.open_sftp() as sftp:
            sftp.put(str(local), remote)

    def get(self, remote: str, local: Path) -> None:
        with self.client.open_sftp() as sftp:
            sftp.get(remote, str(local))


def interactive_shell(cfg: Config | None = None) -> int:
    """Hand the terminal to the system ssh client (OpenSSH ships with Windows 10+)."""
    cfg = cfg or load()
    return subprocess.call([
        "ssh", "-o", "StrictHostKeyChecking=no", "-o", f"UserKnownHostsFile={os.devnull}",
        "-o", "LogLevel=ERROR", f"{cfg.tablet_user}@{cfg.tablet_host}"])
