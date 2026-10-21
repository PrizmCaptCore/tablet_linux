# SPDX-License-Identifier: GPL-2.0-only
"""Device map of the stock board overlay (docs/stock-devmap.txt): per device node its bus,
compatible, status, reg/interrupts, GPIOs and supplies, with references resolved through the
overlay's __fixups__ and local phandles, and PMIC regulators named as in mainline."""
from __future__ import annotations

import re

from tbctl.core.config import REPO

STOCK_DT = REPO / "docs" / "stock-dt"
OVERLAY = STOCK_DT / "overlay-kona-mtp-0x10008.dts"
OUTPUT = REPO / "docs" / "stock-devmap.txt"

# stock regulator label -> mainline name (sm8250 boards: PM8150 = "a", PM8150L = "c")
MAINLINE_REGULATORS = {"pm8150_l": "vreg_l{n}a", "pm8150a_l": "vreg_l{n}c", "pm8150l_l": "vreg_l{n}c",
                       "pm8150_s": "vreg_s{n}a", "pm8150a_s": "vreg_s{n}c"}
# nodes worth listing: addressed devices and the board's named peripherals
INTERESTING = re.compile(r"@|goodix|bq|cs35|ctn|redriver|keyboard|ptp")


def _mainline(label: str | None) -> str | None:
    m = re.match(r"(pm8150a?|pm8150l)_([ls])(\d+)$", label or "")
    return MAINLINE_REGULATORS[f"{m[1]}_{m[2]}"].format(n=m[3]) if m else label


def device_map(overlay: str) -> list[tuple[str, ...]]:
    # "/fragment@N/__overlay__/node:prop:idx" -> label of the referenced base-DT node
    fixups = re.search(r"__fixups__ \{(.*?)\n\t\};", overlay, re.S)[1]
    ref = {r: label for label, refs in re.findall(r"\n\t\t(\S+) = (.*?);", fixups)
           for r in re.findall(r'"([^"]+)"', refs)}
    # phandles defined inside the overlay -> node names
    local = {}
    for m in re.finditer(r"\n(\t+)([\w,@\-.]+) \{\n((?:\1\t.*\n)*?)\1\t*phandle = <(0x[0-9a-f]+)>;", overlay):
        local[int(m[4], 16)] = m[2]
    for m in re.finditer(r"\n\t+([\w,@\-.]+) \{[^{}]*?phandle = <(0x[0-9a-f]+)>;", overlay):
        local.setdefault(int(m[2], 16), m[1])

    rows = []
    fragments = r"\n\tfragment@(\d+) \{\n\t\ttarget = <0xffffffff>;\n\n\t\t__overlay__ \{\n(.*?)\n\t\t\};\n\t\};"
    for fm in re.finditer(fragments, overlay, re.S):
        n, body = fm[1], fm[2]
        target = ref.get(f"/fragment@{n}:target:0", "?")
        for nm in re.finditer(r"\n\t\t\t([\w,@\-.]+) \{\n(.*?)\n\t\t\t\};", "\n" + body, re.S):
            node, props = nm[1], nm[2]
            compatible = re.search(r'compatible = "([^"]+)"', props)
            if not compatible or not INTERESTING.search(node):
                continue
            path = f"/fragment@{n}/__overlay__/{node}"
            items = []
            for pm in re.finditer(r"\n\t\t\t\t([\w,\-]+) = <([^>]*)>;", "\n" + props):
                prop, val = pm[1], pm[2].split()
                if prop.endswith("-supply"):
                    label = ref.get(f"{path}:{prop}:0") or local.get(int(val[0], 16), val[0])
                    items.append(f"{prop}={_mainline(label)}")
                elif "gpio" in prop and val and val[0] == "0xffffffff":
                    items.append(f"{prop}={ref.get(f'{path}:{prop}:0', '?')}:{int(val[1], 16)}")
                elif prop in ("reg", "interrupts"):
                    items.append(f"{prop}=<{' '.join(val)}>")
            status = re.search(r'\n\t\t\t\tstatus = "(\w+)"', "\n" + props)
            rows.append((target, node, compatible[1], "status=" + (status[1] if status else "-"),
                         "; ".join(items)))
    return rows


def generate() -> int:
    rows = device_map(OVERLAY.read_text(encoding="utf-8"))
    OUTPUT.write_text("".join(" | ".join(r) + "\n" for r in rows), encoding="utf-8", newline="\n")
    return len(rows)
