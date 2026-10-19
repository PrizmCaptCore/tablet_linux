"""Copy local files to the tablet's Arch system over SFTP: python tools/tput.py LOCAL... REMOTE_DIR
Uses the same TB_HOST / TB_USER / TB_PASS settings as tssh.py."""
import os
import sys

import paramiko

*locals_, remote_dir = sys.argv[1:]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(os.environ.get("TB_HOST", "172.16.42.1"), username=os.environ.get("TB_USER", "alarm"),
          password=os.environ.get("TB_PASS", "alarm"), timeout=15, allow_agent=False, look_for_keys=False)
s = c.open_sftp()
for f in locals_:
    dst = remote_dir.rstrip("/") + "/" + os.path.basename(f)
    s.put(f, dst)
    print(f"{f} -> {dst} ({os.path.getsize(f)} bytes)")
