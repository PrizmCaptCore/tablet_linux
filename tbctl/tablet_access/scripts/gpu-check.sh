#!/bin/sh
# On the tablet (root): is GNOME rendering on the Adreno GPU?
echo "drm: $(ls /sys/class/drm | tr '\n' ' ')"
lsmod | grep -E '^msm ' | awk '{print "msm loaded, used by", $3}'
g1=$(awk '/gpu-irq/ {print $2}' /proc/interrupts); sleep 3; g2=$(awk '/gpu-irq/ {print $2}' /proc/interrupts)
echo "gpu irqs over 3s: $g1 -> $g2"
journalctl -b --no-pager | grep -E 'Created gbm renderer|selected primary|zap|a650|adreno' | tail -5
for p in $(pgrep -f gnome-shell); do grep -l -E 'msm|freedreno|kgsl' /proc/$p/maps >/dev/null 2>&1; done
grep -h -o -E '[^ ]*(freedreno|msm_dri|swrast|llvmpipe|dri_gbm|libgallium)[^ ]*' /proc/$(pgrep -o -f gnome-shell)/maps 2>/dev/null | sort -u
