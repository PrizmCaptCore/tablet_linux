#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
import os
import re
import sys
import time

CSV, PIDFILE = "/var/tmp/memtrack.csv", "/var/tmp/memtrack.pid"
FIELDS = ("time", "used_mib", "swap_mib", "game_pss_mib", "game_gpu_mib", "game_procs",
          "game_swap_mib", "game_gpu_total_mib")
DRM_UNITS = {"B": 1 / 2**20, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024}


def meminfo():
    m = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":")
            m[k] = int(v.split()[0]) // 1024
    return m["MemTotal"] - m["MemAvailable"], m["SwapTotal"] - m["SwapFree"]


def processes():
    procs = {}
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            with open(f"/proc/{pid}/stat") as f:
                ppid = int(f.read().rsplit(")", 1)[1].split()[1])
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        procs[int(pid)] = (ppid, cmd)
    return procs


def game_tree(procs, appid):
    roots = {p for p, (_, cmd) in procs.items() if f"AppId={appid} " in cmd + " "}
    tree, grew = set(roots), True
    while grew:
        grew = False
        for p, (ppid, _) in procs.items():
            if ppid in tree and p not in tree:
                tree.add(p)
                grew = True
    return tree


def process_mib(pid):
    out = {"Pss:": 0, "SwapPss:": 0}
    try:
        with open(f"/proc/{pid}/smaps_rollup") as f:
            for line in f:
                key = line.split(None, 1)[0]
                if key in out:
                    out[key] = int(line.split()[1]) / 1024
    except OSError:
        pass
    return out["Pss:"], out["SwapPss:"]


def gpu_mib(pids):
    clients = {}
    for pid in pids:
        try:
            fds = os.listdir(f"/proc/{pid}/fdinfo")
        except OSError:
            continue
        for fd in fds:
            try:
                with open(f"/proc/{pid}/fdinfo/{fd}") as f:
                    text = f.read()
            except OSError:
                continue
            cid = re.search(r"^drm-client-id:\s+(\d+)", text, re.M)
            if not cid:
                continue
            sizes = []
            for key in ("resident", "total"):
                m = re.search(rf"^drm-{key}-memory:\s+(\d+) (\w+)", text, re.M)
                sizes.append(int(m[1]) * DRM_UNITS[m[2]] if m else 0)
            clients[cid[1]] = sizes
    return sum(c[0] for c in clients.values()), sum(c[1] for c in clients.values())


def sample(appid, interval):
    with open(CSV, "w") as out:
        out.write(",".join(FIELDS) + "\n")
        while True:
            used, swap = meminfo()
            tree = game_tree(processes(), appid)
            mem = [process_mib(p) for p in tree]
            gpu, gpu_total = gpu_mib(tree)
            out.write(f"{time.strftime('%H:%M:%S')},{used},{swap},{sum(m[0] for m in mem):.0f},"
                      f"{gpu:.0f},{len(tree)},{sum(m[1] for m in mem):.0f},{gpu_total:.0f}\n")
            out.flush()
            time.sleep(interval)


def summary():
    with open(CSV) as f:
        header = f.readline().strip().split(",")
        rows = [dict(zip(header, l.strip().split(","))) for l in f]
    if not rows:
        print("no samples")
        return
    print(f"{len(rows)} samples, {rows[0]['time']} - {rows[-1]['time']}")
    for key, label in (("used_mib", "system RAM in use"), ("swap_mib", "swapped to zram"),
                       ("game_pss_mib", "game processes in RAM"),
                       ("game_swap_mib", "game processes swapped"),
                       ("game_gpu_mib", "game GPU buffers in RAM"),
                       ("game_gpu_total_mib", "game GPU buffers total")):
        if key in header:
            peak = max(rows, key=lambda r: int(r[key]))
            print(f"  {label:24} peak {int(peak[key]):6} MiB at {peak['time']}")
    total = max(int(r["used_mib"]) + int(r["swap_mib"]) for r in rows)
    print(f"  {'RAM + swap':24} peak {total:6} MiB")
    if "game_gpu_total_mib" in header:
        out = max(int(r["game_gpu_total_mib"]) - int(r["game_gpu_mib"]) for r in rows)
        print(f"  {'GPU buffers not in RAM':24} peak {out:6} MiB")


def bar(mib, total, width=30):
    n = min(width, round(mib / total * width)) if total else 0
    return "#" * n + "." * (width - n)


def watch():
    m = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":")
            m[k] = int(v.split()[0]) // 1024
    total = m["MemTotal"]
    print(f"RAM {total / 1024:.1f} GiB, swap {m['SwapTotal'] / 1024:.1f} GiB  (Ctrl+C to stop)",
          flush=True)
    print(f"{'time':8}  {'RAM in use':>10} {'':30}  {'swap':>6}  {'game RAM+swap':>13}  "
          f"{'GPU RAM/total':>13}", flush=True)

    def show(header, line):
        r = dict(zip(header, line.strip().split(",")))
        g = lambda key: f"{int(r.get(key, 0)) / 1024:4.1f}"
        gpu_total = "game_gpu_total_mib" if "game_gpu_total_mib" in r else "game_gpu_mib"
        print(f"{r['time']:8}  {g('used_mib'):>8} G {bar(int(r['used_mib']), total)}  "
              f"{g('swap_mib'):>4} G  {g('game_pss_mib')} + {g('game_swap_mib')} G  "
              f"{g('game_gpu_mib')} / {g(gpu_total)} G", flush=True)

    with open(CSV) as f:
        header = f.readline().strip().split(",")
        for line in f.readlines()[-5:]:
            show(header, line)
        while True:
            line = f.readline()
            if line.endswith("\n"):
                show(header, line)
            else:
                time.sleep(0.5)


def main():
    cmd = sys.argv[1]
    if cmd == "watch":
        if not os.path.exists(PIDFILE):
            print("sampler is not running: start it with `tbctl debug mem start`")
            return
        try:
            watch()
        except KeyboardInterrupt:
            pass
        return
    if cmd == "start":
        appid, interval = sys.argv[2], float(sys.argv[3])
        if os.fork():
            return
        os.setsid()
        with open(PIDFILE, "w") as f:
            f.write(str(os.getpid()))
        sys.stdin.close()
        fd = os.open(os.devnull, os.O_RDWR)
        os.dup2(fd, 1)
        os.dup2(fd, 2)
        sample(appid, interval)
    elif cmd == "stop":
        try:
            with open(PIDFILE) as f:
                os.kill(int(f.read()), 15)
            os.unlink(PIDFILE)
        except (OSError, ValueError):
            print("sampler was not running")
        summary()
    elif cmd == "status":
        summary()


if __name__ == "__main__":
    main()
