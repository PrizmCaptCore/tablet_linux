#!/bin/bash
# WSL: show the value of kernel config symbols:  bash tools/chk-kconfig.sh SYM1 SYM2 ...
source /mnt/e/windows_project/tablet_linux/env.sh
for s in "$@"; do grep -E "^(# )?CONFIG_$s[ =]" "$KERNEL/.config" || echo "CONFIG_$s (absent)"; done
