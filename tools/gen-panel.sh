#!/bin/bash
# WSL: generate a mainline DRM panel driver for the stock RM692H0 panel with
# linux-mdss-dsi-panel-driver-generator (lmdpdg), from base DTB + board overlay merged.
set -eo pipefail
source "$(dirname "$(readlink -f "$0")")/../env.sh"
G=$WORK/lmdpdg
[ -d "$G" ] || git clone -q --depth 1 https://github.com/msm8953-mainline/linux-mdss-dsi-panel-driver-generator "$G"
python3 "$REPO/tools/patch-lmdpdg.py" "$G/panel.py"
S=$WORK/stock
fdtoverlay -i "$S/dtbs/base00.dtb" -o "$S/merged-mtp.dtb" "$S/dtbos/ovl04.dtb"
ls -l "$S/merged-mtp.dtb"
rm -rf "$WORK/panel-gen" && mkdir -p "$WORK/panel-gen" && cd "$WORK/panel-gen"
python3 "$G/lmdpdg.py" --dumb-dcs "$S/merged-mtp.dtb" 2>&1 | tail -20
find . -type f | head -40
