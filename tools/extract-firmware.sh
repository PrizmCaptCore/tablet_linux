#!/bin/bash
# WSL: extract device firmware from the stock ZUI 14 QFIL package into $WORK/stock-fw:
#   modem/   NON-HLOS.bin (FAT): adsp/cdsp/slpi/venus/... signed .mbn/.mdt
#   bt/      BTFM.bin (FAT): QCA6390 Bluetooth firmware
#   vendor/  firmware directories from the vendor logical partition inside super
#   bash tools/extract-firmware.sh /mnt/c/Users/PrizmBlue/tb138fc/zui14/image
set -eo pipefail
source "$(dirname "$(readlink -f "$0")")/../env.sh"
IMAGES=${1:?path to the extracted ZUI firmware image/ directory}
F=$WORK/stock-fw
rm -rf "$F" && mkdir -p "$F"/{modem,bt,vendor,tmp}

mcopy -s -n -i "$IMAGES/NON-HLOS.bin" ::/ "$F/modem/"
mcopy -s -n -i "$IMAGES/BTFM.bin" ::/ "$F/bt/"

# super is shipped as 6 raw chunks; place each at (start_sector - first_sector) * 4096
python3 - "$IMAGES" "$F/tmp/super.img" <<'EOF'
import re, sys, os
images, out = sys.argv[1], sys.argv[2]
xml = open(os.path.join(images, "rawprogram_unsparse0.xml")).read()
chunks = [(f, int(s)) for f, s in re.findall(r'filename="(super_\d+\.img)"[^>]*?start_sector="(\d+)"', xml)]
base = min(s for _, s in chunks)
with open(out, "wb") as o:
    o.truncate(8 * 1024**3)          # super partition is 8 GiB
    for f, s in chunks:
        o.seek((s - base) * 4096)
        with open(os.path.join(images, f), "rb") as i:
            while (b := i.read(1 << 24)):
                o.write(b)
print("super chunks:", len(chunks))
EOF
python3 "$REPO/tools/third_party/lpunpack.py" --partition vendor_a "$F/tmp/super.img" "$F/tmp" 2>/dev/null || \
python3 "$REPO/tools/third_party/lpunpack.py" --partition vendor "$F/tmp/super.img" "$F/tmp"
V=$(ls "$F"/tmp/vendor*.img | head -1)
echo "vendor image: $V ($(blkid -o value -s TYPE "$V" 2>/dev/null || file -b "$V" | cut -c1-40))"
if dump.erofs "$V" >/dev/null 2>&1; then
  fsck.erofs --extract="$F/tmp/vendor-root" "$V" >/dev/null
else
  mkdir -p "$F/tmp/vendor-root" && debugfs -R "rdump / $F/tmp/vendor-root" "$V" >/dev/null 2>&1
fi
for d in firmware firmware_mnt etc/wifi lib/firmware; do
  [ -d "$F/tmp/vendor-root/$d" ] && mkdir -p "$F/vendor/$d" && cp -a "$F/tmp/vendor-root/$d/." "$F/vendor/$d/"
done
rm -rf "$F/tmp/super.img"
echo "== modem"; ls "$F/modem/image" 2>/dev/null | tr '\n' ' '; echo
echo "== bt"; find "$F/bt" -type f | sed "s#$F/bt/##" | tr '\n' ' '; echo
echo "== vendor firmware"; find "$F/vendor" -type f | sed "s#$F/vendor/##" | head -80
