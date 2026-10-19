#!/bin/bash
# WSL: turn the stock firmware extracted by tools/extract-firmware.sh into the layout the
# mainline drivers expect, under $OUT/firmware/usr/lib/firmware/. Proprietary files stay out of git.
#   bash tools/package-firmware.sh
set -eo pipefail
source "$(dirname "$(readlink -f "$0")")/../env.sh"
F=$WORK/stock-fw
[ -d "$F/modem/image" ] || { echo "run tools/extract-firmware.sh first"; exit 1; }

# pil-squasher: merges split .mdt/.bNN images into a single .mbn
PS=$WORK/pil-squasher
if [ ! -x "$PS/pil-squasher" ]; then
  rm -rf "$PS" && git clone -q --depth 1 https://github.com/linux-msm/pil-squasher "$PS"
  make -s -C "$PS"
fi

D=$OUT/firmware/usr/lib/firmware/qcom/sm8250/LENOVO/TB138FC
rm -rf "$OUT/firmware" && mkdir -p "$D"
for n in adsp cdsp slpi venus; do
  "$PS/pil-squasher" "$D/$n.mbn" "$F/modem/image/$n.mdt"
done
"$PS/pil-squasher" "$D/a650_zap.mbn" "$F/vendor/firmware/a650_zap.mdt"

# Cirrus CS35L43 speaker amp DSP firmware/tunings (used once audio is wired up)
mkdir -p "$OUT/firmware/usr/lib/firmware/cirrus"
cp "$F"/vendor/firmware/spk*-cs35l43-* "$OUT/firmware/usr/lib/firmware/cirrus/"

(cd "$OUT/firmware" && find . -type f | sort | xargs ls -l | awk '{print $5, $9}')
tar -C "$OUT/firmware" --owner=0 --group=0 --mode=u=rwX,go=rX -czf "$OUT/firmware-tb138fc.tar.gz" usr
ls -l "$OUT/firmware-tb138fc.tar.gz"
