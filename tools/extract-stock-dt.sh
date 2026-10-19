#!/bin/bash
# WSL: unpack the stock ZUI 14 boot.img/dtbo.img and decompile every DTB / overlay into
# docs/stock-dt/. The board uses dtbo entry ovl04 ("kona MTP", board-id 0x10008).
#   bash tools/extract-stock-dt.sh /mnt/c/Users/PrizmBlue/tb138fc/zui14/image
set -eo pipefail
source "$(dirname "$(readlink -f "$0")")/../env.sh"
IMAGES=${1:?path to the extracted ZUI firmware image/ directory}
T=$WORK/stock && rm -rf "$T" && mkdir -p "$T/dtbs" "$T/dtbos"
unpack_bootimg --boot_img "$IMAGES/boot.img" --out "$T/boot" >/dev/null
python3 - "$T" "$IMAGES/dtbo.img" <<'EOF'
import struct, sys
t, dtbo = sys.argv[1], sys.argv[2]
def split(path, outdir, prefix, skip=0):
    d = open(path, "rb").read(); i = skip; n = 0
    while (j := d.find(b"\xd0\x0d\xfe\xed", i)) >= 0:
        size = struct.unpack(">I", d[j + 4:j + 8])[0]
        if size < 100 or j + size > len(d):
            i = j + 4; continue
        open(f"{outdir}/{prefix}{n:02d}.dtb", "wb").write(d[j:j + size]); n += 1; i = j + size
split(f"{t}/boot/dtb", f"{t}/dtbs", "base")
split(dtbo, f"{t}/dtbos", "ovl", skip=4)
EOF
mkdir -p "$REPO/docs/stock-dt"
for f in "$T"/dtbs/*.dtb "$T"/dtbos/*.dtb; do dtc -I dtb -O dts -q -o "${f%.dtb}.dts" "$f" </dev/null; done
cp "$T/dtbs/base00.dts" "$REPO/docs/stock-dt/base-kona-v2.1.dts"
cp "$T/dtbos/ovl04.dts" "$REPO/docs/stock-dt/overlay-kona-mtp-0x10008.dts"
ls -l "$REPO/docs/stock-dt"
