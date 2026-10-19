#!/bin/bash
V=$HOME/tb138fc/stock-fw/tmp/vendor-root
P=/mnt/e/windows_project/tablet_linux/backup/persist.img
echo "== vendor etc/sensors"; ls $V/etc/sensors 2>&1 | head; echo "config files: $(ls $V/etc/sensors/config 2>/dev/null | wc -l)"
echo "== persist sensors"; debugfs -R "ls -l /sensors" $P 2>/dev/null | head -12; debugfs -R "ls /sensors/registry" $P 2>/dev/null | tr -s ' ' '\n' | grep -v '^$' | head -5
echo "registry entries: $(debugfs -R 'ls /sensors/registry/registry' $P 2>/dev/null | tr -s ' ' '\n' | grep -c .)"
echo "== dspso.bin"; file -b /mnt/c/Users/PrizmBlue/tb138fc/zui14/image/dspso.bin | cut -c1-80
debugfs -R "ls /" /mnt/c/Users/PrizmBlue/tb138fc/zui14/image/dspso.bin 2>/dev/null | tr -s ' ' '\n' | grep -v '^$' | head -10
