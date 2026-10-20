# Progress log

## 2026-10-18 — unlock and first mainline boot

### Bootloader
- Device: TB138FC, SM8250 (kona v2.1), ZUI 15.0.321, 8 GB RAM, Micron 128 GB UFS.
- ZUI 15 abl removed all unlock commands. Downgraded to ZUI 14 over EDL (bkerler/edl `qfil`),
  then `fastboot flashing unlock` worked. The Lenovo `sn.img` route needs a Chinese Lenovo
  account and was not usable; the generic "HAHAHAHA" `sn.img` trick fails on this model
  (abl compares against the UFS serial `e20782b0`, not the fpinfo SN).
- Lenovo abl also has **no `fastboot boot`** → test images are flashed to `boot_a`.
- abl applies the stock `dtbo_a` overlay to whatever DTB it boots; with a mainline DTB this
  fails ("ufdt apply overlay failed") and abl drops to fastboot → `dtbo_a` erased.

### Kernel bring-up (mainline 7.2.11)
| Problem | Cause | Fix |
|---|---|---|
| No USB gadget | `PHY_QCOM_QMP_COMBO` was `=m` (pulled down by `TYPEC=m`), unavailable in initramfs | build TYPEC, DRM_AUX_BRIDGE, QMP combo PHY in |
| Windows saw "ADB interface" | gadget ID `18d1:d001` matched the Google USB driver | use `1d6b:0103` → Windows inbox UsbNcm |
| Screen froze shortly after boot | `SM_DISPCC_8250=y` reprograms the display PLL at probe | keep it `=m` and blacklisted; enable `&mdss` so the display interconnect keeps its vote |
| `pmic-spmi 0-0a/0-0b` errors | there is no PM8009 on this board (J716F has one) | drop `pm8009.dtsi` and its RPMh regulators |
| Fuel gauge NACK on i2c3 | stock overlay lists bq27541 on both se3 and se15; real one is i2c15 | move to `&i2c15` (as in Q706F) |
| Touch "device confirm failed", all-zero reads | GENI hardware chip-select drops between write and read | `cs-gpios = <&tlmm 31>` + GPIO CS pinctrl (as in Q706F) |
| Touch IRQ storm (~1400/s) | level-low IRQ refires until the event is cleared | falling edge (stock `irq-flags = 2`) |

### Debugging techniques that worked
- `fastboot oem logdump` — full UEFI/abl log, shows exactly why abl refused an image.
- When the screen is unusable: initramfs writes `dmesg` to the scratch `logdump` partition,
  reboots to fastboot (`rebootmode bootloader`, PON `mode-bootloader`), then read it over EDL.
- USB NCM + telnet debug shell (`tools/tsh.py`), file push with busybox `nc` (`tools/tpush.py`).
- Stock DT → complete device map (`tools/devmap.py`) instead of guessing one property at a time.

### Lessons
- Look for a working sibling port first. `silime/linux` branch `lenovo-q706f`
  (`dts/ref/sm8250-lenovo-q706f.dts`) solved touch and the fuel gauge immediately and shares
  the panel power layout (vddio l14a, vdd l11c, reset gpio75).
- Dump the stock configuration completely (bus, address, GPIOs, supplies) before writing DTS.

## 2026-10-18 (later) — Arch + GNOME, Wi-Fi, Bluetooth
- Rootfs built under qemu-user in WSL (`rootfs/mkrootfs.sh`): pacman needs `DisableSandbox`
  (no Landlock), `gnome-books`/`gnome-boxes` have broken deps on ALARM, and WSL systemd services
  copy loop mounts into their namespaces → build in `unshare -m`, kill chroot gpg-agent.
- Flashed to `userdata` (sparse, ~11 min); boots to GDM, touch login works, root grows to 107 GB.
- Wi-Fi + BT: only change was the QCA6390 PMU supply — `vddpmu` from PM8150 `s6a`
  (as on lenovo-q706f) instead of PM8009 `s2f`. Stock linux-firmware works for both.
- USB debug net: NCM picks a random host MAC each boot and the DHCP pool had 1 address →
  fixed `dev_addr`/`host_addr`, pool of 8.
- systemd here rejects `systemctl reboot bootloader`; use `--reboot-argument=bootloader`.

## 2026-10-18 (evening) — remoteprocs, display (msm + DSC), GPU

### Remoteprocs
- Stock `adsp/cdsp/slpi/venus.mdt` (NON-HLOS.bin) and `a650_zap.mdt` (vendor) squashed to `.mbn`
  with pil-squasher (`tools/extract-firmware.sh`, `tools/package-firmware.sh`). ADSP/CDSP/SLPI run.
- pacman on the device needed Landlock in the kernel (`SECURITY_LANDLOCK`, LSM list).

### Display + GPU: what the panel actually needs
| Problem | Cause | Fix |
|---|---|---|
| Panel never answered DCS reads, init silently "succeeded" | with `qcom,sync-dual-dsi` mainline drops DCS sent on DSI0 and only fires on DSI1 | `kernel/patches/0001` (sync on DSI0, from the J716F tree) + keep sync |
| Left half only / mirrored half | without sync only DSI0 got init commands | same |
| Noise in every mode | **the panel is DSC** (node named "without DSC", but timing nodes set `compression-mode = "dsc"`: 1280x8 slice per link, 10 bpc, 8 bpp) | DSC config + PPS + compression-mode in the panel driver |
| Slot `_a` unbootable, abl stuck in fastboot | A/B retry counter ran out (Linux never marked the slot successful) | `fastboot set_active a`; `tb138fc-boot-success.service` (qbootctl -m) |

Final configuration: full stock init sequence (lmdpdg `--dumb-dcs`), command mode, DSC, bonded DSI
with `qcom,sync-dual-dsi`, 60 Hz mode with per-link porches doubled (msm halves them).

### How the DSC was found
Dumped the display registers twice with `tools/disp-regdump.sh` (`logs/regs/`): once with msm
blacklisted (bootloader state, known good) and once under msm, then diffed. Bootloader:
`CTL_DSC_ACTIVE=3`, DSI stream word count 1281 bytes for 1280 pixels (3:1). That one diff
explained hours of noise/mirroring experiments.

### Lessons
- When a bootloader already drives the hardware correctly, dump its registers and diff against
  ours before experimenting.
- Stock DT names/comments can be wrong; read the actual properties (timing sub-nodes too).
- Reference tree for this panel family: `ungeskriptet/linux` branch `sm8250-next` (J716F dual DSI).

### Bluetooth (fixed after it was wrongly marked working)
- Firmware loading is not "working": the GNOME toggle flipped back off. `bluetooth.service` was
  not enabled, and the QCA6390 stayed an *unconfigured controller* (no public BD address).
- Android's `btwlansn` copies the addresses from fpinfo (`+0xa0` Bluetooth, `+0xc0` Wi-Fi) to
  persist; `rootfs/tb138fc-macs` does the same at boot (`btmgmt public-addr` once the QCA
  firmware download has finished, Wi-Fi MAC before NetworkManager). Verified power-on + scan.
- It still failed on some boots: the service raced the fpinfo device node and exited quietly.
  Now `Requires=`/`After=` the `dev-disk-by-partlabel-fpinfo.device` unit; 3/3 reboots OK.

### Display polish
- Refresh rate is panel register page 0x40 / 0xbd (stock timing-switch-command): 0x00 = 120 Hz,
  0x05 = 60 Hz. Driver defaults to 120 Hz (stock timing@0), `refresh=60` module option.
- DCS brightness 0-2047 verified across the range (GNOME slider uses it).
- Remaining cosmetic: "DSI PLL lock failed" warning at PHY probe (harmless; modeset relocks).

### Sensors (SLPI)
- Stack: hexagonrpcd serves stock files (`tools/build-hexagonfs.sh`) to the SLPI; libssc +
  iio-sensor-proxy (Arch repos) expose accel / light / compass to GNOME.
- hexagonrpcd must be started by udev when `/dev/fastrpc-sdsp` appears (fastrpc is a module;
  a plain multi-user service is skipped by its ConditionPathExists).
- The SLPI re-parses all configs and rewrites the registry on every boot. Stock hexagonrpcd
  refuses writes (endless `temp.json` retries) -> vendored write-support patches from the
  Galaxy Tab S8+ port (`rootfs/hexagonrpcd-patches/`), writable copy in /var/lib/hexagonrpcd.
- SLPI crashed twice per boot, 20 s after attach ("SEE Sensor exceeded processing time
  limit"). Verbose hexagonrpcd showed the stall right after opening `sns_bring_to_ear.so`
  (dynamic sensor module) -> dropped the dynamic modules from hexagonfs. 0 crashes since.
- Lesson: count crashes with `journalctl -k`, not `dmesg | grep -c` - the "Handover
  signaled" spam (1/s) wraps the ring buffer and hid crashes; that briefly blamed the
  absent BMI3x0/QMI8658 accel candidates wrongly.
- Accel is the ICM4x6xx; X/Y swapped vs the panel: ACCEL_MOUNT_MATRIX "0,1,0;-1,0,0;0,0,1".

### Speakers (4x CS35L43)
- No mainline CS35L43 driver: vendored the 7.2 port of Cirrus' Android driver from the
  Xiaomi Pad 6S Pro (sheng) kernel (`kernel/cs35l43/`); needs `cs_dsp_load_coeff` exported
  (patch 0003) and the card driver must clock every amp via component sysclk (patch 0002).
- Stock wires the amps as PRI TDM, but the same mi2s0 pins run plain I2S like sheng:
  `PRIMARY_MI2S_RX`, `qcom,sd-lines = <1>` (gpio140 = stock pri_tdm_dout). All four answer
  on i2c4 once reset gpio131 is high; shared reset/irq handled by the driver.
- Stock mixer_paths "speaker" path -> UCM: protection firmware (Lenovo Harman tuning),
  DSP RX1/RX2 = ASPRX1/2, gain 17. Left SPK3/SPK4 (slot 0), right SPK1/SPK2 (slot 1),
  mapped by ear (one amp at a time).
- Quiet output = no factory calibration. persist/audio/spk_N_{cal_r,ambient} (ASCII) ->
  `tb138fc-spk-cal` -> sysfs `calibration` -> driver writes CAL_R/AMBIENT/STATUS/CHECKSUM.
  This firmware marks CAL_R read-only, so cs_dsp coeff writes fail (-EPERM); the driver
  writes the XM words directly (`cs_dsp_write_data_word`).
- Shared amp irq (gpio68, level low) needs the stock pull-up: the TLMM default pull-down kept
  it asserted -> ~200 irq/s and 4 irq threads hammering i2c4. Fixed with a pin state on
  speaker-amp@40; `gpioget --bias` is useless for testing this (bias reverts on release).
- Don't stop the user's PipeWire for raw `aplay` tests (it removed the sound device in GNOME).
- Seen once: CDSP "failed to authenticate image" + ADSP announcing no QRTR services (no
  sound card); fine after reboot. Watch for recurrence.

### Charging (PM8150B SMB5)
- Without a driver the SMB5 ran on bootloader defaults (~0.9 A). Mainline qcom_smbx only knows
  SMB2; SMB5 support is a posted series (Robin Snyders / Casey Connolly, v4 2026-08-20) on top
  of a 5-patch fixes series and a power_supply init() hook from the power-supply tree. Rebuilt
  against 7.2.11 as kernel/patches 0004-0012 (0004 syncs qcom_smbx.c with 7.3, 0012 backports
  the init() hook).
- buildkernel.sh used a reverse dry-run to skip applied patches; that misfires for series
  touching the same lines (half-applied hunks). Applied patches are now recorded in
  $KERNEL/.tb138fc-patches.
- DT: pm8150b.dtsi (was missing - J716F lacks it), charger@1000 with stock irqs, ADC5
  USB_IN_I/USB_IN_V_16, simple-battery (also monitored by bq27541).
- Float voltage: stock battery-data says 4.485 V, but its node carries Qualcomm's reference
  cell name and the cell spec is unconfirmed. First boot at 4.48 V charged a full battery
  towards it; charging was suspended (`echo Unknown > .../pm8150b-charger/status` = USBIN
  suspend) and the float lowered to 4.45 V.
- Input: APSD sees the PC port as SDP (500 mA) but hardware AICL settles at 2 A on this port
  (4.65 V x 1.98 A). DCP chargers get 1.5 A; 3 A needs Type-C Rp/PD (TCPM).

### USB-C / PD / clock
- PM8150B Type-C (TCPM) wired like the RB5 (same NB7VPQ904M redriver). dwc3 is otg with
  role-switch-default-mode = peripheral, so the NCM debug link comes up before TCPM (module).
  Step 1 (sink/device only) then step 2 (dual role, OTG VBUS) - debug link survived both.
- Sink PDOs: 5 V only - the SMB5 series doesn't program USBIN_ADAPTER_ALLOW for 9 V+. Not
  worth it while charge current is capped at 2.4 A (and the system idles properly: cpufreq-hw
  + schedutil, ~90-98 % in cpu-sleep, GPU at min).
- TCPM's power supply knows the Type-C/PD current, qcom_smbx only BC1.2. `tb138fc-usb-icl`
  (udev) copies it to the charger; SMB5 ignores USBIN_CURRENT_LIMIT_CFG without the ICL
  override bit, hence patch 0013 (explicit limit -> override; BC1.2 path clears it).
- OTG verified with USB-C earphones. The tablet rebooted once during that test (cause unknown).
- Clock: rtc-pm8xxx is read-only and the RTC only counts since the last PMIC reset, so every
  boot started in 1970 until NTP (Firefox: "potential security threat"). `tb138fc-rtc` saves
  real-time minus RTC after NTP sync / at shutdown and restores it at boot (RTC_DRV_PM8XXX
  built in; waiting for dev-rtc0.device as a module hit the 90 s device timeout).
- BLE keyboard (HID-over-GATT) paired but typed nothing: BlueZ needs /dev/uhid and
  CONFIG_UHID was off (BT_HIDP only covers classic BT). Now built as a module.

### Display off/on (screen timeout)
- After the first DPMS off/on the panel stayed broken with `dsi_err_worker: status=4` (DSI
  FIFO error) ~30k/s. Register diff boot vs resume (tools/disp-regdump.sh): DSI1 FIFO status
  0x9999xxxx (HS FIFO underflow on all lanes) and DSI1 PHY CMN_CLK_CFG0 0xf1 instead of 0x61.
- msm saves/restores only the master PLL state, and nothing ever programs the bonded slave's
  CMN_CLK_CFG0 - it only worked while the bootloader's value survived the first PHY reset.
  kernel/patches/0014 mirrors the master's dividers to the slave in restore_state.
- Reproduce/test remotely: Mutter `org.gnome.Mutter.DisplayConfig.PowerSaveMode` 3/0 on the
  session bus of whoever owns the seat (gdm-greeter at the login screen).
- Careful: reading the DSC registers (0xae80000) with regdump while unclocked crashed the tablet.

## Mics (WCD938x)
- Built-in mics are analog on a WCD938x (no headset jack), like the kona MTP: sm8250-mtp.dts
  wcd938x + swr1/swr2 + rx/tx macros, stock micbias 2.4 V. Capture link TX_CODEC_DMA_TX_3 via
  MultiMedia2; routes need the SM8250 TX macro names (TX SWR_ADC0/1), not SM8450's
  TX SWR_INPUTx - a wrong route name killed the whole card (speakers too).
- amic1 (stock handset-mic) verified: noise floor -82 dBFS, speech/claps up to -42 dBFS.
  UCM "Mic" device (mono, ADC1 analog gain 12 dB). The MultiMedia2 FE route must be in the
  verb EnableSequence: PipeWire probes PCMs before enabling devices, and an unrouted FE fails
  to open, which drops the whole HiFi profile (speakers too).
- Speakers intermittently unusable ~20 s after boot (runtime PM "error" on all amps): the
  CS35L43 driver only fell back to POWER_ON_SEQUENCE (firmware < 7.15.3; Lenovo's is 7.13.1)
  on -EINVAL, but mainline cs_dsp returns -ENOENT for a missing control. Fixed in
  kernel/cs35l43/cs35l43.c.

### Bluetooth crash loop
- Seen once in ~30 boots (boot of 2026-10-20 23:10, ~100 s in): "unexpected event for opcode
  0xe000/0x2400", command 0xfc00 tx timeout, then every re-setup ended in a controller
  hardware error and hci_qca crashed the chip for a memdump - 120 times, every 3.5 s, until
  reboot. Trigger not reproduced; hci_qca's own recovery never got out of it.
- `tb138fc-bt-watchdog`: 3 "crash the soc" in 60 s -> unbind/bind hci_uart_qca (full power
  sequence off/on; Wi-Fi unaffected), max once per 10 min, keeps the first controller dump in
  /var/lib/tb138fc-bt. Verified by injecting the message via /dev/kmsg.
- A re-probed controller is unconfigured again, so the BD address is now set by
  `tb138fc-bt-addr.service`, started from udev on every hci0 add (tb138fc-macs bt|wifi).
- BT_RFCOMM / BT_BNEP were missing (bluetoothd: RFCOMM server failed) -> HFP/HSP and PAN enabled.

### DP alt mode (external monitor)
- mdss_dp + QMP combo PHY + connector altmodes as on the RB5 (data-lanes 0-3 for DP-only
  adapters). TCPM entered DP mode and the HPD Attention reached msm_dp, but every DPCD read
  timed out (AUX -110): the AUX channel runs over the USB-C SBU pins, which this board routes
  through an FSA4480 (i2c15 @0x43, ID 0xf1; stock qcom,dp-aux-switch), not the redriver as on
  the RB5. Connector SBU endpoint -> fcs,fsa4480 node fixed it.
- Verified with a VIA/Terminus USB-C hub (pin assignment D, 2 lanes HBR2): 3840x2160@30,
  3 adapter attaches + 2 PC re-attaches in one boot, link training OK each time, no AUX errors.
  4K60 needs a 4-lane (pin assignment C) adapter; SM8250 DP tops out around 4K60.
- Debug: `echo 0x106 > /sys/module/drm/parameters/debug` (driver+KMS+DP) and the TCPM log in
  /sys/kernel/debug/usb/tcpm-*/log; test without the USB link via Wi-Fi (TB_HOST).

## Next
2. Audio input: microphones (WCD938x / VA macro DMICs), USB-C headset.
3. Charging: PM8150B Type-C/TCPM for 3 A / PD input (watch the usb0 debug link), JEITA/step
   charging, SMB1396/SMB1398 charge pumps (no driver). Boot-time load-average burst (~100-160
   in the first ~40 s, then idle) - not yet explained.
