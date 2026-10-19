#!/bin/bash
# WSL: rebuild only the RM692H0 panel module and stage it at $OUT/panel-raydium-rm692h0.ko
set -eo pipefail
source "$(dirname "$(readlink -f "$0")")/../env.sh"
cd "$KERNEL"
cp "$REPO/kernel/panel/panel-raydium-rm692h0.c" drivers/gpu/drm/panel/
make -s -j"$(nproc)" modules 2>&1 | { grep -v "Warning (" || true; }
aarch64-linux-gnu-strip --strip-debug -o "$OUT/panel-raydium-rm692h0.ko" drivers/gpu/drm/panel/panel-raydium-rm692h0.ko
ls -l "$OUT/panel-raydium-rm692h0.ko"
