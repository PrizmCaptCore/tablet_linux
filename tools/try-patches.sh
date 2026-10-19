#!/bin/bash
# WSL: dry-run kernel/patches/*.patch against the kernel tree (forward and reverse)
source /mnt/e/windows_project/tablet_linux/env.sh
cd "$KERNEL"
for p in "$REPO"/kernel/patches/*.patch; do
  f=$(patch -p1 --dry-run -s -f < "$p" >/dev/null 2>&1 && echo applies || echo no)
  r=$(patch -p1 -R --dry-run -s -f < "$p" >/dev/null 2>&1 && echo already-in || echo no)
  echo "$(basename $p): forward=$f reverse=$r"
done
