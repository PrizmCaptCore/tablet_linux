# TB138FC hardware notes

Source: stock ZUI 14 `boot.img` (header v2, embedded DTB, kona v2.1, msm-id 0x164/0x20001) +
`dtbo.img` overlay for board-id 0x10008 ("kona MTP" — Lenovo reuses Qualcomm reference IDs).
Decompiled copies: [stock-dt/](stock-dt/) (re-extract with `tbctl firmware stock-dt`).
Per-device bus/GPIO/supply table: [stock-devmap.txt](stock-devmap.txt) (`tools/devmap.py`).
Mainline bus names: `qupv3_seN_i2c` → `&i2cN`, `qupv3_seN_spi` → `&spiN`;
PMIC regulators `pm8150_lN` → `vreg_lNa`, `pm8150a_lN` → `vreg_lNc`.

| Block | Part | Connection | Mainline status |
|---|---|---|---|
| SoC | SM8250 (kona v2.1), 8 GB RAM, Micron 128 GB UFS 3.1 | | ✅ |
| GPU | Adreno 650 | zap shader `qcom/sm8250/LENOVO/TB138FC/a650_zap.mbn` | ✅ Freedreno |
| PMICs | PM8150, PM8150B, PM8150L (**no PM8009**) | SPMI | ✅ regulators via RPMh |
| Display | Raydium **RM692H0** OLED, dual-DSI command mode **with DSC** (despite the stock name "without DSC"): 1280x8 slice per link, 10 bpc, 8 bpp; 2560×1536 (1280×1536 per DSI), 120/60 Hz, 245×146 mm | vddio `l14a`, vdd `l11c` (3.3 V), avdd 5.5 V gpio61 regulator, lab/ibb; reset gpio75, TE gpio66 | ✅ `kernel/panel/panel-raydium-rm692h0.c` (120 Hz; 0x40/0xbd selects 120/60) |
| Touch | Goodix **GT9966S** (Berlin-B) | spi0, CS gpio31 (GPIO CS), reset gpio38, irq gpio39 falling, AVDD enable gpio108 | ✅ `goodix,gt9916` |
| Keyboard pack | Lenovo keyboard (MCU) | i2c1 @0x60 (irqs gpio54/129), touchpad i2c3 @0x61 (irq gpio11), vdd `l16a`, vddl `l8c` | disabled, untested |
| Speakers | 4× Cirrus **CS35L43** (left: SPK3 @0x43, SPK4 @0x40; right: SPK1 @0x41, SPK2 @0x42) | i2c4 @0x40-0x43, VA `s4a`, shared irq gpio68 + reset gpio131; audio on mi2s0 (gpio138-141, playback data1); stock uses PRI TDM | ✅ `kernel/cs35l43/` (from sheng port) + protection fw + calibration (persist/audio/spk_N_cal_r) |
| Audio codec | WCD938x (no headset jack; mics only) + LPASS rx/tx/va macros | reset gpio32, s4a supplies, micbias 1-3 2.4 V (stock), SoundWire swr1 (RX) / swr2 (TX) | ✅ amic1 built-in mic (stock handset-mic) |
| Fuel gauge | TI **bq27541** | i2c15 @0x55 | ✅ (8000 mAh design) |
| Sensors | **ICM4x6xx** accel/gyro (SSC SPI 3, DRI gpio123), **AK0991x** compass (SSC I2C 1), **MN29xxx** light (SSC I2C 5), hall; registry also lists absent BMI3x0/QMI8658/MMC56x3x | owned by the SLPI | ✅ hexagonrpcd + libssc + iio-sensor-proxy, mount matrix `0,1,0;-1,0,0;0,0,1` |
| Charger | PM8150B SMB5 + **SMB1396** ×2 (@0x34/0x35) + **SMB1398** (@0x36); battery L22D2P31 8000 mAh, stock float 4.485 V | SMB5 on SPMI sid 2 @0x1000; charge pumps i2c15 | ✅ SMB5 main charger (4.45 V / 2.4 A, AICL); charge pumps and Type-C PD TODO |
| Wi-Fi / BT | QCA6390 (PCIe0 / UART6) | PMU from PM8150 s6a; wlan-en gpio20, bt-en gpio21, bt-sw-ctrl gpio124; calibration in the persist partition; MACs in fpinfo (+0xa0 BT, +0xc0 Wi-Fi) | ✅ stock linux-firmware; addresses set by `tb138fc-macs` |
| USB-C | dwc3 + QMP combo PHY, onnn NB7VPQ904M redriver @0x19 (i2c13, vcc l16a 3.0-3.3 V as stock), PM8150B Type-C/PD PHY, DP alt mode | | ✅ dual role + PD sink 5 V + OTG VBUS (1.5 A) + DP alt mode (SBU/AUX via FSA4480 @0x43 on i2c15, stock qcom,dp-aux-switch); USB 3 untested (only a USB 2 cable so far) |
| Buttons | power (PON), volume down (PON resin), volume up (pm8150 gpio6) | | ✅ |
| Other | NXP CTN730 (pen charger) @0x28, Goodix fingerprint (vdd `l10c`), Airoha GPS, cameras | | low priority |

## Stock kernel command line hints
`msm_drm.dsi_display0=qcom,mdss_dsi_dual_rm692h0_2k_cmd:` — abl selects the RM692H0 panel.
abl appends `androidboot.*`, `rootwait ro init=/init` to our cmdline.
