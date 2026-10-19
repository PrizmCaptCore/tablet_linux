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
- Don't stop the user's PipeWire for raw `aplay` tests (it removed the sound device in GNOME).
- Seen once: CDSP "failed to authenticate image" + ADSP announcing no QRTR services (no
  sound card); fine after reboot. Watch for recurrence.

## Next
2. Audio input: microphones (WCD938x / VA macro DMICs), USB-C headset.
3. Charging: SMB1396 ×2 + SMB1398 on i2c15; verify PM8150B charging under Linux.
