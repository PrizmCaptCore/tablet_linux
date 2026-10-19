#!/bin/bash
# Build the TB138FC kernel (Image.gz, DTB, modules) in WSL.
#   bash kernel/buildkernel.sh
set -eo pipefail
source "$(dirname "$(readlink -f "$0")")/../env.sh"
KVER_UPSTREAM=7.2.11

# kernel tree (plain upstream stable tarball)
if [ ! -d "$KERNEL" ]; then
  mkdir -p "$WORK" && cd "$WORK"
  curl -sL "https://cdn.kernel.org/pub/linux/kernel/v7.x/linux-$KVER_UPSTREAM.tar.xz" -o linux.tar.xz
  mkdir linux && tar -xf linux.tar.xz -C linux --strip-components=1 && rm linux.tar.xz
fi
cd "$KERNEL"

# device tree
cp "$REPO/dts/$DTS_NAME.dts" arch/arm64/boot/dts/qcom/
grep -q "$DTS_NAME.dtb" arch/arm64/boot/dts/qcom/Makefile || \
  sed -i "s/^dtb-\$(CONFIG_ARCH_QCOM)\t+= sm8250-hdk.dtb/&\ndtb-\$(CONFIG_ARCH_QCOM)\t+= $DTS_NAME.dtb/" arch/arm64/boot/dts/qcom/Makefile

# kernel patches (kernel/patches/*.patch), applied once (skipped when already in the tree)
for p in "$REPO"/kernel/patches/*.patch; do
  [ -e "$p" ] || continue
  if patch -p1 -R --dry-run -s -f < "$p" >/dev/null 2>&1; then continue; fi
  patch -p1 -s -f < "$p" && echo "applied $(basename "$p")"
done

# out-of-tree panel driver (kernel/panel/): Raydium RM692H0
cp "$REPO/kernel/panel/panel-raydium-rm692h0.c" drivers/gpu/drm/panel/
cat > drivers/gpu/drm/panel/Kconfig.tb138fc <<'EOF'
config DRM_PANEL_RAYDIUM_RM692H0
	tristate "Raydium RM692H0 dual-DSI panel (Lenovo TB138FC)"
	depends on OF && DRM_MIPI_DSI && BACKLIGHT_CLASS_DEVICE
	select DRM_DISPLAY_DSC_HELPER
	select DRM_DISPLAY_HELPER
EOF
grep -q 'Kconfig.tb138fc' drivers/gpu/drm/panel/Kconfig || \
  sed -i '/^config DRM_PANEL_RAYDIUM_RM69380$/i source "drivers/gpu/drm/panel/Kconfig.tb138fc"\n' drivers/gpu/drm/panel/Kconfig
grep -q 'panel-raydium-rm692h0.o' drivers/gpu/drm/panel/Makefile || \
  echo 'obj-$(CONFIG_DRM_PANEL_RAYDIUM_RM692H0) += panel-raydium-rm692h0.o' >> drivers/gpu/drm/panel/Makefile

# out-of-tree speaker amp driver (kernel/cs35l43/): Cirrus CS35L43, from the sheng port
cp "$REPO"/kernel/cs35l43/cs35l43{.c,.h,-i2c.c,-tables.c} sound/soc/codecs/
cp "$REPO/kernel/cs35l43/sound-cs35l43.h" include/sound/cs35l43.h
grep -q 'config SND_SOC_CS35L43$' sound/soc/codecs/Kconfig || \
  sed -i '/^config SND_SOC_CS35L45$/i config SND_SOC_CS35L43\n\ttristate\n\tselect SND_SOC_WM_ADSP\n\nconfig SND_SOC_CS35L43_I2C\n\ttristate "Cirrus Logic CS35L43 CODEC (I2C)"\n\tdepends on I2C\n\tselect REGMAP_I2C\n\tselect SND_SOC_CS35L43\n' sound/soc/codecs/Kconfig
grep -q 'snd-soc-cs35l43-i2c' sound/soc/codecs/Makefile || \
  printf '%s\n' 'snd-soc-cs35l43-i2c-y := cs35l43-i2c.o cs35l43.o cs35l43-tables.o' \
    'obj-$(CONFIG_SND_SOC_CS35L43_I2C)	+= snd-soc-cs35l43-i2c.o' >> sound/soc/codecs/Makefile

# config: arm64 defconfig + everything the initramfs needs before modules are available
make -s defconfig
Y="PINCTRL_SM8250 SM_GCC_8250 SM_GPUCC_8250 INTERCONNECT_QCOM_SM8250 QCOM_RPMHPD QCOM_RPMH REGULATOR_QCOM_RPMH
   QCOM_GENI_SE I2C_QCOM_GENI SPI_QCOM_GENI SERIAL_QCOM_GENI QCOM_GPI_DMA
   SCSI_UFS_QCOM SCSI_UFSHCD SCSI_UFSHCD_PLATFORM PHY_QCOM_QMP PHY_QCOM_QMP_UFS PHY_QCOM_QMP_COMBO PHY_QCOM_QMP_USB PHY_QCOM_USB_SNPS_FEMTO_V2
   USB_DWC3 USB_DWC3_QCOM USB_GADGET USB_LIBCOMPOSITE USB_CONFIGFS USB_CONFIGFS_NCM USB_CONFIGFS_ECM USB_CONFIGFS_RNDIS USB_CONFIGFS_ACM USB_F_NCM USB_U_ETHER
   DRM DRM_SIMPLEDRM SYSFB_SIMPLEFB FB FRAMEBUFFER_CONSOLE
   SPMI SPMI_MSM_PMIC_ARB MFD_SPMI_PMIC PINCTRL_QCOM_SPMI_PMIC INPUT_PM8941_PWRKEY KEYBOARD_GPIO
   BATTERY_BQ27XXX BATTERY_BQ27XXX_I2C QCOM_SPMI_ADC5 QCOM_PDC QCOM_SCM QCOM_COMMAND_DB QCOM_AOSS_QMP
   TOUCHSCREEN_GOODIX_BERLIN_CORE TOUCHSCREEN_GOODIX_BERLIN_SPI INPUT_EVDEV
   TYPEC DRM_AUX_BRIDGE DRM_AUX_HPD_BRIDGE INTERCONNECT_QCOM_OSM_L3 POWER_RESET_QCOM_PON NVMEM_REBOOT_MODE
   BLK_DEV_INITRD DEVTMPFS DEVTMPFS_MOUNT EXT4_FS VFAT_FS"
for o in $Y; do scripts/config -e $o; done
# Must NOT be built in: probing it reprograms the display PLL and freezes the panel
# (it is loaded later together with msm, which then drives the panel itself).
scripts/config -m SM_DISPCC_8250
scripts/config -m DRM_MSM -m DRM_PANEL_RAYDIUM_RM692H0
scripts/config -m SND_SOC_CS35L43_I2C -m SND_SOC_SM8250
# Landlock: pacman's download sandbox needs it
scripts/config -e SECURITY_LANDLOCK --set-str LSM "landlock,lockdown,yama,integrity,bpf"
scripts/config -d LOCALVERSION_AUTO --set-str LOCALVERSION "-tb138fc"
make -s olddefconfig
for o in $Y; do
  v=$(grep -E "^CONFIG_$o=" .config || echo "CONFIG_$o (missing)")
  case "$v" in *=y) ;; *) echo "not built-in: $v";; esac
done

time make -s -j"$(nproc)" Image.gz dtbs modules 2>&1 | { grep -v -E "Warning \(|^\s*$" || true; } | tail -15
ls -l arch/arm64/boot/Image.gz "arch/arm64/boot/dts/qcom/$DTS_NAME.dtb"
echo "kernel: $(make -s kernelrelease)"
