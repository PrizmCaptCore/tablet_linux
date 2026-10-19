#!/bin/bash
# getapk.sh PKG: download an Alpine aarch64 package and extract it into ~/tb138fc/apk/PKG
set -e
cd ~/tb138fc
R=https://dl-cdn.alpinelinux.org/alpine/v3.24/${REPO:-main}/aarch64
curl -s $R/APKINDEX.tar.gz | tar -xzO APKINDEX > APKINDEX
V=$(awk -v p="$1" 'BEGIN{RS=""} $0 ~ "\nP:" p "\n" {print}' APKINDEX | grep '^V:' | cut -d: -f2)
echo "$1 $V"
curl -sLo /tmp/$1.apk $R/$1-$V.apk
mkdir -p apk/$1 && tar -xzf /tmp/$1.apk -C apk/$1 2>/dev/null || true
find apk/$1 -type f -path '*bin/*'
