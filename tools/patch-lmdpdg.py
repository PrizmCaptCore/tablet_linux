"""Make lmdpdg find panels on Lenovo kona DTs: their qcom,dsi-display nodes reference the panel
via qcom,dsi-default-panel instead of qcom,dsi-panel, and some display nodes have no panel."""
import sys

p = sys.argv[1]
s = open(p).read()
old = "\t\t\t\tpanel_phandles.add(fdt.getprop(display, 'qcom,dsi-panel').as_uint32())\n\t\t\telse:"
new = ("\t\t\t\tph = fdt.getprop_or_none(display, 'qcom,dsi-panel') or "
       "fdt.getprop_or_none(display, 'qcom,dsi-default-panel')\n"
       "\t\t\t\tif ph is not None:\n"
       "\t\t\t\t\tpanel_phandles.add(ph.as_uint32())\n"
       "\t\t\telse:")
if "dsi-default-panel" not in s:
    assert old in s, "lmdpdg layout changed; update tools/patch-lmdpdg.py"
    open(p, "w").write(s.replace(old, new))
print("lmdpdg patched")
