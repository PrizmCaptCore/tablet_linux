# Recovery

All commands from Windows. `fastboot` = `%LOCALAPPDATA%\Android\platform-tools\fastboot.exe`.
Firmware: `C:\Users\PrizmBlue\tb138fc\zui14\image` (ZUI 14 `Q00024.0_S_ZUI_14.0.625_ST_220901` QFIL package).

## Get into fastboot / EDL

| Mode | How |
|---|---|
| fastboot (abl) | power off, hold **Volume Down** + power on; from our Linux: `rebootmode bootloader` |
| EDL (9008) | `fastboot oem reboot-edl`; or with the tablet off hold **Volume Up** while plugging USB |
| Bootloader log | `fastboot oem logdump` (shows why abl refused to boot, e.g. DTBO overlay failure) |

Windows drivers: fastboot uses a WinUSB (libwdi) driver whose `DeviceInterfaceGUIDs` was set to
`{F72FE0D4-CBCB-407D-8814-9ED673D0DD6B}`; EDL uses WinUSB via Zadig on `05C6:9008`.

## Back to stock Android (ZUI 14)

```
fastboot flash boot_a  C:\Users\PrizmBlue\tb138fc\zui14\image\boot.img
fastboot flash dtbo_a  C:\Users\PrizmBlue\tb138fc\zui14\image\dtbo.img
fastboot erase userdata
fastboot reboot
```

## Full reflash / unbrick (EDL)

From `C:\Users\PrizmBlue\tb138fc\edl`, with `PYTHONUTF8=1` (the progress bar crashes under cp949):

```
..\venv\Scripts\python.exe edl.py qfil rawprogram_unsparse0.xml,rawprogram1.xml,rawprogram2.xml,rawprogram3.xml,rawprogram4.xml,rawprogram5.xml patch0.xml,patch1.xml,patch2.xml,patch3.xml,patch4.xml,patch5.xml ..\zui14\image --memory=ufs --loader=..\zui14\image\prog_firehose_ddr.elf
```

The rawprogram files leave `persist`, `fpinfo`, `frp`, `devinfo`, `modemst*`, `fsg`, `fsc` untouched
(no filename), and the GPT layout matches the device (verified against `logs/printgpt.log`).

## Device-unique partitions

`backup/` holds EDL dumps taken before any write (checksums in `backup/SHA256SUMS`):
`persist` (Wi-Fi/sensor calibration), `fpinfo` (Lenovo SN `<device serial>`, Wi-Fi/BT MACs),
`frp` (last byte `01` = OEM unlock allowed), `devinfo`, `modemst1/2`, `fsg`, `fsc`.
Restore one with: `edl.py w <partition> <file> --memory=ufs --loader=...prog_firehose_ddr.elf`.

## Bootloader unlock (what worked)

1. ZUI 15 abl: every unlock command is `unknown command`.
2. QFIL-flash ZUI 14 over EDL (data wiped; requires "OEM unlocking" enabled beforehand).
3. ZUI 14 abl: `fastboot flashing unlock`, confirm on the tablet with the volume/power keys.
   No Lenovo `sn.img` (China-only account) was needed.
