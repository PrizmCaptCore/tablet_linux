Cirrus Logic CS35L43 boosted smart amp driver (4 on i2c4 @0x40-0x43; no mainline driver).

Taken from the Xiaomi Pad 6S Pro (sheng) mainline kernel, a 7.2 port of Cirrus's
Android driver: https://github.com/ianchb/sm8550-mainline (branch sheng-7.2.10),
sound/soc/codecs/cs35l43{.c,.h,-i2c.c,-tables.c} and include/sound/cs35l43.h.

`tbctl kernel build` copies them into the tree (sound-cs35l43.h -> include/sound/cs35l43.h)
and adds SND_SOC_CS35L43{,_I2C} to sound/soc/codecs/Kconfig and Makefile.
The PLL is set up by the component set_sysclk (BCLK as reference), so the machine driver
must call snd_soc_component_set_sysclk() for each amp (kernel/patches/0002).

Local change: speaker calibration (sysfs `calibration` = "CAL_R ambient", applied when the
DSP starts; see rootfs/tb138fc-spk-cal). The calibration words are written straight into
XM because this protection firmware marks CAL_R/CAL_STATUS/CAL_CHECKSUM read-only.
