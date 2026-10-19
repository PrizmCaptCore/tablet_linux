"""Compare the stock RM692H0 timing nodes (on/switch commands, framerate) from the decompiled overlay."""
import re, os
HERE = os.path.dirname(os.path.abspath(__file__))
o = open(os.path.join(HERE, "..", "docs", "stock-dt", "overlay-kona-mtp-0x10008.dts")).read()
i = o.index("qcom,mdss_dsi_dual_rm692h0_2k_cmd {")
panel = o[i:o.index("\n\t\t\t};", i)]
def cmds(blob):
    b = [int(x, 16) for x in blob.split()]
    out, p = [], 0
    while p + 7 <= len(b):
        dtype, last, vc, ack, wait, l1, l2 = b[p:p + 7]
        n = (l1 << 8) | l2
        out.append((hex(dtype), " ".join(f"{x:02x}" for x in b[p + 7:p + 7 + n]), wait))
        p += 7 + n
    return out
for t in re.finditer(r"(timing@\d) \{(.*?)\n\t\t\t\t\t\};", panel, re.S):
    name, body = t.group(1), t.group(2)
    fr = re.search(r"framerate = <(0x[0-9a-f]+)>", body).group(1)
    print(f"== {name}: {int(fr, 16)} Hz")
    for prop in ("qcom,mdss-dsi-on-command", "qcom,mdss-dsi-timing-switch-command", "qcom,mdss-dsi-off-command"):
        m = re.search(prop + r" = \[(.*?)\];", body, re.S)
        if m:
            c = cmds(m.group(1))
            print(f"  {prop}: {len(c)} cmds")
            if "switch" in prop:
                for x in c: print("     ", x)
            setattr(__import__("builtins"), name.replace("@", "_") + prop.split("-")[-2], c)
import builtins
a, b = builtins.timing_0on, builtins.timing_1on
diff = [(n, x, y) for n, (x, y) in enumerate(zip(a, b)) if x != y]
print(f"on-command diffs timing@0 vs timing@1 ({len(a)} vs {len(b)} cmds):")
for n, x, y in diff: print(f"  #{n}: {x[1]}  ->  {y[1]}")
