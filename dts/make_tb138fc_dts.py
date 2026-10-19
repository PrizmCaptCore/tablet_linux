"""Derive the initial TB138FC devicetree from the J716F one (stock-DT findings in ../docs/HARDWARE.md)."""
import difflib
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'ref', 'sm8250-lenovo-j716f.dts'), encoding='utf-8').read()
s = src


def sub(old, new):
    global s
    assert old in s, old[:80]
    s = s.replace(old, new)


sub(""" * Copyright (c) 2025, David Wronek <david@xxxxxxxxxxxxxx>
 */""", """ * Copyright (c) 2025, David Wronek (sm8250-lenovo-j716f.dts)
 *
 * Lenovo Xiaoxin Pad Pro 2022 (TB138FC), derived from the J716F devicetree.
 * Initial bring-up: UFS, USB (peripheral), simple-framebuffer, buttons, fuel gauge.
 */""")
sub('model = "Lenovo Xiaoxin Pad Pro 2021";', 'model = "Lenovo Xiaoxin Pad Pro 2022";')
sub('compatible = "lenovo,j716f", "qcom,sm8250";', 'compatible = "lenovo,tb138fc", "qcom,sm8250";')
sub('qcom,board-id = <0x2010008 0>;', 'qcom,board-id = <0x10008 0>, <0x2010008 0>, <0x3010008 0>;')
sub('height = <1600>;', 'height = <1536>;')

# Keyboard pack: stock DT has keyboard@60 on i2c1 (irqs gpio54/gpio129) and touchpad@61 on i2c3 (irq gpio11).
sub("""	touchpad@60 {
		compatible = "hid-over-i2c";
		reg = <0x60>;""", """	/* Stock: keyboard@60, irqs on gpio54/gpio129; not yet verified */
	keyboard@60 {
		compatible = "hid-over-i2c";
		reg = <0x60>;""")
sub("""		interrupts = <14 IRQ_TYPE_LEVEL_LOW>;

		hid-descr-addr = <0x01>;
		post-power-on-delay-ms = <100>;
	};""", """		interrupts = <54 IRQ_TYPE_LEVEL_LOW>;

		hid-descr-addr = <0x01>;
		post-power-on-delay-ms = <100>;
		status = "disabled";
	};""")
s = re.sub(r"""	/\* onsemi NB7VPQ904M USB redriver @ 19 \*/
(	/\* CS35L41 audio amp @ 4\d \*/\n)+
	keyboard@61 \{.*?\n	\};
""", """	/* CS35L43 audio amp @ 40 */
	/* CS35L43 audio amp @ 41 */
	/* CS35L43 audio amp @ 42 */
	/* CS35L43 audio amp @ 43 */
""", s, flags=re.S)
assert 'keyboard@61' not in s
sub("""	fuel-gauge@55 {
		compatible = "ti,bq27541";
		reg = <0x55>;
	};
""", """	/* Stock: keyboard-pack touchpad, irq on gpio11; not yet verified */
	touchpad@61 {
		compatible = "hid-over-i2c";
		reg = <0x61>;

		vdd-supply = <&vreg_l16a_3p3>;
		vddl-supply = <&vreg_l8c_1p8>;

		pinctrl-names = "default";
		pinctrl-0 = <&mcu_default>;

		interrupt-parent = <&tlmm>;
		interrupts = <11 IRQ_TYPE_LEVEL_LOW>;

		hid-descr-addr = <0x01>;
		post-power-on-delay-ms = <100>;
		status = "disabled";
	};
""")
sub("	/* GT7385P touchscreen @ 5d */", "	/* onsemi USB redriver @ 19 */\n	/* NXP CTN730 @ 28 */")
sub("""	/* SMB1390 charger @ 10 */
	/* ES7210 audio ADC @ 40 */
	/* FSA4480 USB audio switch @ 43 */
	/* RTC6226 FM receiver @ 64 */
	/* HL6111R wireless charging IC @ 25 */
""", """	/* Qcom SMB1396 @ 34, SMB1396 slave @ 35, SMB1398 @ 36 */

	/* Stock overlay lists bq27541 on both se3 and se15; it NACKs on i2c3, and lenovo-q706f uses i2c15 */
	fuel-gauge@55 {
		compatible = "ti,bq27541";
		reg = <0x55>;
	};
""")

# Remoteprocs and GPU zap shader: stock firmware squashed by tools/package-firmware.sh.
for n in ['adsp', 'cdsp', 'slpi', 'venus']:
    sub(f'firmware-name = "qcom/sm8250/LENOVO/J716F/{n}.mbn";',
        f'firmware-name = "qcom/sm8250/LENOVO/TB138FC/{n}.mbn";')
sub('"qcom/sm8250/LENOVO/J716F/a650_zap.mbn"', '"qcom/sm8250/LENOVO/TB138FC/a650_zap.mbn"')

# Lets Linux "reboot bootloader" land in fastboot (same as other SM8250 boards).
sub("&pon_pwrkey {", """&pon {
	mode-bootloader = <0x2>;
	mode-recovery = <0x1>;
};

&pon_pwrkey {""")

# No PM8009 on this board: SPMI SIDs 0xa/0xb NACK and RPMh has no "smpf1" resource.
sub('#include "pm8009.dtsi"\n', '')
s = re.sub(r'\n\tregulators-2 \{\n\t\tcompatible = "qcom,pm8009-rpmh-regulators";.*?\n\t\};\n', '\n', s, flags=re.S)
assert 'pm8009' not in s and 'vreg_s1f' not in s
# Wi-Fi/BT PMU: J716F feeds vddpmu from PM8009 s2f, which this board lacks; lenovo-q706f
# (same SoC/PMIC set) feeds vddaon/vddpmu/vddrfa0p95 all from PM8150 s6a.
sub("\t\tvddpmu-supply = <&vreg_s2f_0p5>;\n", "\t\tvddpmu-supply = <&vreg_s6a_0p6>;\n")

# MDSS: msm display + GPU. Being an interconnect consumer it also keeps display bandwidth
# voted between boot and msm probe (otherwise sync_state freezes the splash panel).
sub("&pcie0 {", "&mdss {\n\tstatus = \"okay\";\n};\n\n&pcie0 {")

# Touchscreen: Goodix GT9966S (Berlin) on SPI0. Stock: avdd enable gpio108, reset gpio38,
# irq gpio39 falling, 2560x1536, 1 MHz. Upstream has no gt9966 entry; GT9966 is Berlin-B,
# which uses the Berlin-D (gt9916) SPI framing.
sub("""	qca6390-pmu {""", """	ts_avdd: regulator-ts-avdd {
		compatible = "regulator-fixed";
		regulator-name = "ts_avdd";
		regulator-min-microvolt = <3300000>;
		regulator-max-microvolt = <3300000>;

		gpio = <&tlmm 108 GPIO_ACTIVE_HIGH>;
		enable-active-high;
		startup-delay-us = <10000>;

		pinctrl-names = "default";
		pinctrl-0 = <&ts_avdd_en>;
	};

	qca6390-pmu {""")
sub("&ufs_mem_hc {", """&qup_spi0_cs_gpio {
	drive-strength = <6>;
	bias-disable;
};

&qup_spi0_data_clk {
	drive-strength = <6>;
	bias-disable;
};

&spi0 {
	/* GPIO chip-select keeps CS asserted across the Berlin write+read (as on lenovo-q706f) */
	pinctrl-names = "default";
	pinctrl-0 = <&qup_spi0_data_clk>, <&qup_spi0_cs_gpio>;
	cs-gpios = <&tlmm 31 GPIO_ACTIVE_LOW>;
	status = "okay";

	touchscreen@0 {
		compatible = "goodix,gt9916";
		reg = <0>;
		spi-max-frequency = <1000000>;

		interrupts-extended = <&tlmm 39 IRQ_TYPE_EDGE_FALLING>;
		reset-gpios = <&tlmm 38 GPIO_ACTIVE_LOW>;
		avdd-supply = <&ts_avdd>;

		pinctrl-names = "default";
		pinctrl-0 = <&ts_int_default>, <&ts_reset_default>;

		touchscreen-size-x = <2560>;
		touchscreen-size-y = <1536>;
	};
};

&ufs_mem_hc {""")
sub("""	wlan_en: wlan-en-state {""", """	ts_avdd_en: ts-avdd-en-state {
		pins = "gpio108";
		function = "gpio";
		drive-strength = <2>;
		bias-disable;
	};

	ts_int_default: ts-int-default-state {
		pins = "gpio39";
		function = "gpio";
		drive-strength = <2>;
		bias-pull-up;
		input-enable;
	};

	ts_reset_default: ts-reset-default-state {
		pins = "gpio38";
		function = "gpio";
		drive-strength = <2>;
		bias-disable;
	};

	wlan_en: wlan-en-state {""")

# Display: RM692H0 dual-DSI command-mode DSC panel (kernel/panel/panel-raydium-rm692h0.c).
# Wiring matches the J716F/RM69380 binding example (avdd gpio61, vddio l14a, reset gpio75) plus
# the stock vdd (l11c); TE on gpio66 (mdp_vsync). Bonded DSI as on the J716F
# (ungeskriptet/linux sm8250-next): qcom,sync-dual-dsi + kernel/patches/0001.
sub("""	qca6390-pmu {""", """	panel_avdd: regulator-panel-avdd {
		compatible = "regulator-fixed";
		regulator-name = "panel_avdd";
		regulator-min-microvolt = <5500000>;
		regulator-max-microvolt = <5500000>;

		gpio = <&tlmm 61 GPIO_ACTIVE_HIGH>;
		enable-active-high;
		regulator-boot-on;

		pinctrl-names = "default";
		pinctrl-0 = <&panel_avdd_en>;
	};

	qca6390-pmu {""")
sub("""		vreg_l11c_3p3: ldo11 {
			regulator-name = "vreg_l11c_3p0";
			regulator-min-microvolt = <3104000>;""", """		vreg_l11c_3p3: ldo11 {
			regulator-name = "vreg_l11c_3p3";
			regulator-min-microvolt = <3300000>;	/* panel vdd: stock 3.3 V */""")
sub("&pcie0 {", """&mdss_dsi0 {
	vdda-supply = <&vreg_l9a_1p2>;
	qcom,dual-dsi-mode;
	/* with kernel/patches/0001: DCS sent on DSI0 is broadcast to both links */
	qcom,sync-dual-dsi;
	qcom,master-dsi;
	status = "okay";

	panel@0 {
		compatible = "lenovo,tb138fc-rm692h0";
		reg = <0>;

		vddio-supply = <&vreg_l14a_1p88>;
		vdd-supply = <&vreg_l11c_3p3>;
		avdd-supply = <&panel_avdd>;
		reset-gpios = <&tlmm 75 GPIO_ACTIVE_LOW>;

		pinctrl-names = "default";
		pinctrl-0 = <&panel_reset>, <&panel_te>;

		ports {
			#address-cells = <1>;
			#size-cells = <0>;

			port@0 {
				reg = <0>;

				panel_in_0: endpoint {
					remote-endpoint = <&mdss_dsi0_out>;
				};
			};

			port@1 {
				reg = <1>;

				panel_in_1: endpoint {
					remote-endpoint = <&mdss_dsi1_out>;
				};
			};
		};
	};
};

&mdss_dsi0_out {
	data-lanes = <0 1 2 3>;
	remote-endpoint = <&panel_in_0>;
};

&mdss_dsi0_phy {
	vdds-supply = <&vreg_l5a_0p88>;
	status = "okay";
};

&mdss_dsi1 {
	vdda-supply = <&vreg_l9a_1p2>;
	qcom,dual-dsi-mode;
	qcom,sync-dual-dsi;
	/* bonded mode: msm itself slaves this PHY to DSI0's PLL (as on J716F) */
	status = "okay";
};

&mdss_dsi1_out {
	data-lanes = <0 1 2 3>;
	remote-endpoint = <&panel_in_1>;
};

&mdss_dsi1_phy {
	vdds-supply = <&vreg_l5a_0p88>;
	status = "okay";
};

&pcie0 {""")
sub("""	wlan_en: wlan-en-state {""", """	panel_avdd_en: panel-avdd-en-state {
		pins = "gpio61";
		function = "gpio";
		drive-strength = <8>;
		bias-disable;
	};

	panel_reset: panel-reset-state {
		pins = "gpio75";
		function = "gpio";
		drive-strength = <8>;
		bias-disable;
	};

	panel_te: panel-te-state {
		pins = "gpio66", "gpio67";
		function = "mdp_vsync";
		drive-strength = <2>;
		bias-pull-down;
	};

	wlan_en: wlan-en-state {""")
# Speakers: 4x CS35L43 on i2c4 (stock: shared reset gpio131, shared irq gpio68, VA s4a,
# DSP firmware spkN-cs35l43-dsp1-spk-prot.*). Stock Android drives them over primary TDM;
# the same mi2s0 pins run plain I2S here (as on the CS35L43-based Xiaomi Pad 6S Pro), with
# playback on data1 (gpio140, stock "pri_tdm_dout").
sub("""	/* CS35L43 audio amp @ 40 */
	/* CS35L43 audio amp @ 41 */
	/* CS35L43 audio amp @ 42 */
	/* CS35L43 audio amp @ 43 */
""", "".join(f"""
	cs35l43_spk{n}: speaker-amp@{addr:x} {{
		compatible = "cirrus,cs35l43";
		reg = <0x{addr:x}>;
		interrupts-extended = <&tlmm 68 IRQ_TYPE_LEVEL_LOW>;
		reset-gpios = <&tlmm 131 GPIO_ACTIVE_HIGH>;
		VA-supply = <&vreg_s4a_1p8>;
		VP-supply = <&vph_pwr>;
		#sound-dai-cells = <0>;
		sound-name-prefix = "SPK{n}";
		cirrus,dsp-part-name = "spk{n}-cs35l43";
		cirrus,bst-ipk-ma = <3200>;	/* stock boost-peak-milliamp */
		cirrus,asp-sdout-hiz = <3>;
		cirrus,vpbr-enable = <1>;
		cirrus,vpbr-atk-vol = <2>;
		cirrus,vpbr-max-att = <6>;
		cirrus,vpbr-thld = <21>;
	}};
""" for addr, n in ((0x40, 4), (0x41, 1), (0x42, 2), (0x43, 3))))
sub("""	vph_pwr: regulator-vph-pwr {""", """	sound {
		compatible = "qcom,sm8250-sndcard";
		model = "Lenovo-TB138FC";
		pinctrl-0 = <&pri_mi2s_active>;
		pinctrl-names = "default";

		mm1-dai-link {
			link-name = "MultiMedia1";

			cpu {
				sound-dai = <&q6asmdai MSM_FRONTEND_DAI_MULTIMEDIA1>;
			};
		};

		speaker-dai-link {
			link-name = "Speakers";

			cpu {
				sound-dai = <&q6afedai PRIMARY_MI2S_RX>;
			};

			platform {
				sound-dai = <&q6routing>;
			};

			codec {
				sound-dai = <&cs35l43_spk1>, <&cs35l43_spk2>,
					    <&cs35l43_spk3>, <&cs35l43_spk4>;
			};
		};
	};

	vph_pwr: regulator-vph-pwr {""")
sub("&pcie0 {", """&q6afedai {
	dai@10 {
		reg = <PRIMARY_MI2S_RX>;
		qcom,sd-lines = <1>;
	};
};

&q6asmdai {
	dai@0 {
		reg = <0>;
	};
};

&pcie0 {""")
sub('#include <dt-bindings/regulator/qcom,rpmh-regulator.h>\n',
    '#include <dt-bindings/phy/phy.h>\n#include <dt-bindings/regulator/qcom,rpmh-regulator.h>\n'
    '#include <dt-bindings/sound/qcom,q6afe.h>\n#include <dt-bindings/sound/qcom,q6asm.h>\n')
assert 'LENOVO/J716F' not in s
open(os.path.join(HERE, 'sm8250-lenovo-tb138fc.dts'), 'w', encoding='utf-8', newline='\n').write(s)
diff = list(difflib.unified_diff(src.splitlines(), s.splitlines(), lineterm='', n=0))
print(len(diff), 'diff lines')
