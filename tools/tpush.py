"""Copy a local file to the tablet over the USB network: tpush.py LOCAL REMOTE [mode]."""
import socket
import sys
import time

from tsh import run

local, remote = sys.argv[1], sys.argv[2]
mode = sys.argv[3] if len(sys.argv) > 3 else "755"
data = open(local, "rb").read()

# Receiver on the tablet: a backgrounded busybox nc (stdin detached from the telnet pty).
run(f"rm -f /tmp/.rx; (nc -l -p 5555 > /tmp/.rx) </dev/null >/dev/null 2>&1 &")
time.sleep(1)
with socket.create_connection(("172.16.42.1", 5555), timeout=10) as s:
    s.sendall(data)
    s.shutdown(socket.SHUT_WR)
time.sleep(1)
print(run(f"mv /tmp/.rx {remote} && chmod {mode} {remote}; wc -c < {remote}"), "bytes on tablet,", len(data), "sent")
