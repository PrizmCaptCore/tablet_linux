#!/bin/sh
# On the tablet (root): dump display-path registers (DPU blocks, DSI controllers, DSI PHY/PLL).
#   sh disp-regdump.sh OUTFILE      (from the PC: tbctl debug regs)
# Offsets: DPU blocks from dpu_6_0_sm8250.h relative to the mdp region at 0xae01000.
# Do not add the DSC blocks (0xae80000): reading them while unclocked crashed the tablet.
OUT=${1:-/tmp/disp-regs.txt}
# Reading a powered-down block hangs the bus and resets the tablet (it did, with the screen
# blanked by the idle timeout): only dump while every block is runtime-active.
for dev in ae00000.display-subsystem ae01000.display-controller ae94000.dsi ae96000.dsi; do
  status=$(cat /sys/bus/platform/devices/$dev/power/runtime_status 2>/dev/null)
  if [ "$status" != active ]; then
    echo "refusing: $dev is '${status:-unknown}' (screen off?); turn the screen on and retry" >&2
    exit 2
  fi
done
/usr/local/bin/regdump \
  mdp_top:0xae01000:0x494 \
  ctl0:0xae02000:0x1e0 ctl1:0xae02200:0x1e0 \
  lm0:0xae45000:0x320 lm1:0xae46000:0x320 \
  intf1:0xae6b800:0x2c0 intf2:0xae6c000:0x2c0 \
  pp0:0xae71000:0xd4 pp1:0xae71800:0xd4 \
  dsi0:0xae94000:0x400 dsi1:0xae96000:0x400 \
  dsi0_phy:0xae94400:0x200 dsi0_lane:0xae94600:0x280 dsi0_pll:0xae94900:0x260 \
  dsi1_phy:0xae96400:0x200 dsi1_lane:0xae96600:0x280 dsi1_pll:0xae96900:0x260 \
  > "$OUT"
echo "$(wc -l < "$OUT") registers -> $OUT"
