# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import socket
import time
from pathlib import Path

from tbctl.core.config import load
from tbctl.core.process import BuildError

IAC, DONT, DO, WONT, WILL = 255, 254, 253, 252, 251
MARK = "__TBCTL_DONE__"


def _strip_negotiation(sock: socket.socket, data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == IAC and i + 2 < len(data):
            cmd, opt = data[i + 1], data[i + 2]
            if cmd in (DO, DONT):
                sock.sendall(bytes([IAC, WONT, opt]))
            elif cmd in (WILL, WONT):
                sock.sendall(bytes([IAC, DONT, opt]))
            i += 3
        else:
            out.append(data[i])
            i += 1
    return bytes(out)


def run(cmd: str, timeout: float = 60) -> str:
    host = load().tablet_host
    try:
        s = socket.create_connection((host, 23), timeout=10)
    except OSError as e:
        raise BuildError(f"rescue shell {host}:23: {e}") from None
    with s:
        s.settimeout(1)
        time.sleep(0.5)
        try:
            _strip_negotiation(s, s.recv(65536))
        except socket.timeout:
            pass
        s.sendall(f"stty -echo 2>/dev/null; {cmd}; echo {MARK}\n".encode())
        buf = b""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                chunk = s.recv(65536)
            except socket.timeout:
                continue
            if not chunk:
                break
            buf += _strip_negotiation(s, chunk)
            if MARK.encode() in buf.split(b"echo " + MARK.encode())[-1]:
                break
    text = buf.decode("utf-8", "replace").replace("\r", "")
    if f"echo {MARK}" in text:
        text = text.split(f"echo {MARK}")[-1]
    return text.replace(MARK, "").strip()


def push(local: Path, remote: str, mode: str = "755") -> str:
    host = load().tablet_host
    data = local.read_bytes()
    run("rm -f /tmp/.rx; (nc -l -p 5555 > /tmp/.rx) </dev/null >/dev/null 2>&1 &")
    time.sleep(1)
    with socket.create_connection((host, 5555), timeout=10) as s:
        s.sendall(data)
        s.shutdown(socket.SHUT_WR)
    time.sleep(1)
    size = run(f"mv /tmp/.rx {remote} && chmod {mode} {remote}; wc -c < {remote}")
    return f"{local} -> {remote}: {size} of {len(data)} bytes"
