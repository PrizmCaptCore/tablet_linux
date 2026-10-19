"""Run a command on the tablet's Arch system over SSH (USB network 172.16.42.1).
   python tools/tssh.py [--root] 'command'      (needs: pip install paramiko)
User/password default to the Arch Linux ARM defaults; override with TB_USER / TB_PASS;
TB_HOST selects another address (e.g. the tablet's Wi-Fi IP)."""
import os
import sys

import paramiko

args = sys.argv[1:]
as_root = bool(args) and args[0] == "--root"
if as_root:
    args = args[1:]
cmd = " ".join(args) if args else sys.stdin.read()
user = os.environ.get("TB_USER", "alarm")
password = os.environ.get("TB_PASS", "alarm")
if as_root:
    # sshd forbids root password login; go through sudo with the user's password
    cmd = f"echo {password!r} | sudo -S -p '' sh -c {cmd!r}"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(os.environ.get("TB_HOST", "172.16.42.1"), username=user, password=password, timeout=15,
          allow_agent=False, look_for_keys=False)
_, out, err = c.exec_command(cmd, timeout=600)
sys.stdout.reconfigure(encoding="utf-8")
sys.stdout.write(out.read().decode("utf-8", "replace"))
sys.stdout.write(err.read().decode("utf-8", "replace"))
sys.exit(out.channel.recv_exit_status())
