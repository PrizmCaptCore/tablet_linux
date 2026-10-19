"""Run a shell command on the tablet's debug initramfs over telnet (172.16.42.1:23)."""
import socket
import sys
import time

IAC, DONT, DO, WONT, WILL = 255, 254, 253, 252, 251
MARK = "__TSH_DONE__"


def strip_negotiation(sock, data):
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


def run(cmd, timeout=60):
    s = socket.create_connection(("172.16.42.1", 23), timeout=10)
    buf = b""
    s.settimeout(1)
    time.sleep(0.5)
    try:
        buf += strip_negotiation(s, s.recv(65536))
    except socket.timeout:
        pass
    s.sendall(f"stty -echo 2>/dev/null; {cmd}; echo {MARK}\n".encode())
    buf = b""
    end = time.time() + timeout
    while time.time() < end:
        try:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += strip_negotiation(s, chunk)
            if MARK.encode() in buf.split(b"echo " + MARK.encode())[-1]:
                break
        except socket.timeout:
            continue
    s.close()
    text = buf.decode("utf-8", "replace").replace("\r", "")
    text = text.split(f"echo {MARK}")[-1] if f"echo {MARK}" in text else text
    return text.replace(MARK, "").strip()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(run(" ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()))
