"""Build a device map from the stock overlay: bus, address, compatible, gpios, supplies (resolved via __fixups__/phandles)."""
import re, os
HERE = os.path.dirname(os.path.abspath(__file__))
o = open(os.path.join(HERE, "..", "docs", "stock-dt", "overlay-kona-mtp-0x10008.dts")).read()
base = open(os.path.join(HERE, "..", "docs", "stock-dt", "base-kona-v2.1.dts")).read()
fix = re.search(r"__fixups__ \{(.*?)\n\t\};", o, re.S).group(1)
ref = {}  # "/fragment@N/__overlay__/node:prop:idx" -> label
for lab, refs in re.findall(r"\n\t\t(\S+) = (.*?);", fix):
    for r in re.findall(r'"([^"]+)"', refs):
        ref[r] = lab
# local phandles inside the overlay -> node names
local = {}
for m in re.finditer(r"\n(\t+)([\w,@\-.]+) \{\n((?:\1\t.*\n)*?)\1\t*phandle = <(0x[0-9a-f]+)>;", o):
    local[int(m.group(4), 16)] = m.group(2)
for m in re.finditer(r"\n\t+([\w,@\-.]+) \{[^{}]*?phandle = <(0x[0-9a-f]+)>;", o):
    local.setdefault(int(m.group(2), 16), m.group(1))
# walk fragments
MAINLINE = {"pm8150_l": "vreg_l{n}a", "pm8150a_l": "vreg_l{n}c", "pm8150l_l": "vreg_l{n}c", "pm8150_s": "vreg_s{n}a", "pm8150a_s": "vreg_s{n}c"}
def ml(lab):
    m = re.match(r"(pm8150a?|pm8150l)_([ls])(\d+)$", lab or "")
    return MAINLINE[m.group(1) + "_" + m.group(2)].format(n=m.group(3)) if m else lab
rows = []
for fm in re.finditer(r"\n\tfragment@(\d+) \{\n\t\ttarget = <0xffffffff>;\n\n\t\t__overlay__ \{\n(.*?)\n\t\t\};\n\t\};", o, re.S):
    n, body = fm.group(1), fm.group(2)
    target = ref.get(f"/fragment@{n}:target:0", "?")
    for nm in re.finditer(r"\n\t\t\t([\w,@\-.]+) \{\n(.*?)\n\t\t\t\};", "\n" + body, re.S):
        node, props = nm.group(1), nm.group(2)
        comp = re.search(r'compatible = "([^"]+)"', props)
        if not comp or not re.search(r"@|goodix|bq|cs35|ctn|redriver|keyboard|ptp", node):
            continue
        path = f"/fragment@{n}/__overlay__/{node}"
        items = []
        for pm in re.finditer(r"\n\t\t\t\t([\w,\-]+) = <([^>]*)>;", "\n" + props):
            prop, val = pm.group(1), pm.group(2).split()
            if prop.endswith("-supply"):
                lab = ref.get(f"{path}:{prop}:0") or local.get(int(val[0], 16), val[0])
                items.append(f"{prop}={ml(lab)}")
            elif "gpio" in prop and val and val[0] == "0xffffffff":
                lab = ref.get(f"{path}:{prop}:0", "?")
                items.append(f"{prop}={lab}:{int(val[1],16)}")
            elif prop in ("reg", "interrupts"):
                items.append(f"{prop}=<{' '.join(val)}>")
        st = re.search(r'status = "(w+)"', props)
        fst = re.search(r'^				status = "(w+)"', body, re.M)
        rows.append((target, node, comp.group(1), "status=" + (st.group(1) if st else "-"), "; ".join(items)))
for r in rows:
    print(" | ".join(r))
