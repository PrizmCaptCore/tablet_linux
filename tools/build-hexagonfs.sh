#!/bin/bash
# WSL: assemble the hexagonrpcd file tree ("hexagonfs") from stock files and pack it as
# $OUT/hexagonfs-tb138fc.tar.gz -> /usr/share/qcom/sm8250/Lenovo/TB138FC on the tablet.
# Layout (see hexagonrpcd(1)):
#   acdb               <- /vendor/etc/acdbdata
#   dsp                <- /vendor/dsp (dsp partition, dspso.bin)
#   sensors/config     <- /vendor/etc/sensors/config
#   sensors/registry   <- persist /sensors/registry/registry
#   sensors/sns_reg_version <- persist /sensors/registry/sns_reg_version
#                         (seeds the writable registry, see rootfs/install-hexagonrpcd.sh)
#   sensors/sns_reg.conf <- /vendor/etc/sensors/sns_reg_config
#   socinfo            <- /sys/devices/soc0 (Android values; MTP board, SM8250 v2.1)
#   bash tools/build-hexagonfs.sh /mnt/c/Users/PrizmBlue/tb138fc/zui14/image
set -eo pipefail
source "$(dirname "$(readlink -f "$0")")/../env.sh"
IMAGES=${1:?path to the extracted ZUI firmware image/ directory}
V=$WORK/stock-fw/tmp/vendor-root
[ -d "$V/etc/sensors" ] || { echo "run tools/extract-firmware.sh first"; exit 1; }
PERSIST=$REPO/backup/persist.img
T=$WORK/hexagonfs-root
D=$T/usr/share/qcom/sm8250/Lenovo/TB138FC
rm -rf "$T" && mkdir -p "$D"/{dsp,sensors/config,socinfo,acdb}   # sensors/registry is created by rdump

debugfs -R "rdump / $D/dsp" "$IMAGES/dspso.bin" >/dev/null 2>&1
rm -rf "$D/dsp/lost+found"
cp -a "$V/etc/sensors/config/." "$D/sensors/config/"
cp "$V/etc/sensors/sns_reg_config" "$D/sensors/sns_reg.conf"
debugfs -R "rdump /sensors/registry/registry $D/sensors" "$PERSIST" >/dev/null 2>&1
debugfs -R "dump /sensors/registry/sns_reg_version $D/sensors/sns_reg_version" "$PERSIST" >/dev/null 2>&1
[ -d "$V/etc/acdbdata" ] && cp -a "$V/etc/acdbdata/." "$D/acdb/"

# Dynamic sensor modules (bring-to-ear, WiGig sensing; phone features): the SLPI stalls loading
# sns_bring_to_ear.so over FastRPC and its watchdog kills the sensor process 20 s later
# ("SEE Sensor exceeded processing time limit"), twice per boot. The SLPI re-parses the
# configs on every boot, so drop their configs as well as their registry groups.
rm -f "$D/sensors/config/"{kona_dynamic_sensors,sns_bring_to_ear,wigig_sensing_0}.json \
	"$D/sensors/registry/"{sns_dynamic_sensors,sns_bring_to_ear,wigig_sensing}* \
	"$D/dsp/sdsp/"{sns_bring_to_ear,wigig_sensing}.so

printf 'MTP\n' > "$D/socinfo/hw_platform"
printf 'Unknown\n' > "$D/socinfo/platform_subtype"
printf '0\n' > "$D/socinfo/platform_subtype_id"
printf '65536\n' > "$D/socinfo/platform_version"
printf '2.1\n' > "$D/socinfo/revision"
printf '356\n' > "$D/socinfo/soc_id"

echo "dsp: $(find "$D/dsp" -type f | wc -l) files ($(ls "$D/dsp" | tr '\n' ' '))"
echo "sensors/config: $(ls "$D/sensors/config" | wc -l), registry: $(ls "$D/sensors/registry" | wc -l), acdb: $(find "$D/acdb" -type f | wc -l)"
tar -C "$T" --owner=0 --group=0 --mode=u=rwX,go=rX -czf "$OUT/hexagonfs-tb138fc.tar.gz" usr
ls -l "$OUT/hexagonfs-tb138fc.tar.gz"
