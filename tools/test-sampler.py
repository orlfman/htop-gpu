#!/usr/bin/env python3
"""Tests for src/htop/linux/AMDGPU.c through the amdgpu-sample driver.

1. snapshot: copy the 9070 XT's sysfs files into a fake tree and check every value exactly
2. faults: modified copies of that tree (suspended card, missing or garbage files, other cards,
   RDNA 2 and RDNA 3 cards, integrated graphics, cards without a fan)
3. cache: a monotonicMs that is not newer never re-reads sysfs
4. live: the real /sys at idle, then during a VA-API encode on the 9070 XT

Needs src/htop configured (./configure). Run: python3 -I test-sampler.py
"""
import glob, json, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True  # keep tools/ free of __pycache__
sys.path.insert(0, HERE)
import gpu_metrics  # noqa: E402

PCI = "0000:04:00.0"
REAL_DEV = f"/sys/bus/pci/devices/{PCI}"
RENDER = f"/dev/dri/by-path/pci-{PCI}-render"

GC_DIR = "ip_discovery/die/0/GC/0"
DEVICE_FILES = ["vendor", "device", "revision", f"{GC_DIR}/major", f"{GC_DIR}/minor", f"{GC_DIR}/revision",
                "pp_dpm_sclk", "gpu_busy_percent", "mem_busy_percent", "vcn_busy_percent",
                "mem_info_vram_used", "mem_info_vram_total", "pp_dpm_mclk", "gpu_metrics",
                "power/runtime_status"]
HWMON_PREFIXES = ("name", "power1_", "temp", "freq", "fan1_")
DYNAMIC = ["gpuBusy", "memBusy", "vcnBusy", "vramUsed", "power", "powerCap", "sclk", "mclk",
           "memRate", "vclk", "dclk", "fan"]
LABELS = ["edge", "junction", "mem"]
SCLK_SEED = 3000.0
MEM_RATE_MULTIPLIER = 16
ABSENT_TRIES = 5

# graphics core version -> (chip, GPU clock seed; None = top pp_dpm_sclk level)
CHIPS = {(10, 3, 0): ("Navi 21", None), (10, 3, 2): ("Navi 22", None), (10, 3, 4): ("Navi 23", None),
         (10, 3, 5): ("Navi 24", None), (11, 0, 0): ("Navi 31", None), (11, 0, 2): ("Navi 33", None),
         (11, 0, 3): ("Navi 32", None), (12, 0, 0): ("Navi 44", None), (12, 0, 1): ("Navi 48", SCLK_SEED)}
# the fake binary's own amdgpu.ids, with the kinds of lines libdrm's file has
IDS_TEXT = """# List of AMDGPU IDs
#
# Syntax:
# device_id,	revision_id,	product_name        <-- single tab after comma

1.0.0
73BF,	C0,	AMD Radeon RX 6900 XT
73BF,	C1,	AMD Radeon RX 6800 XT
744C,	C8,	AMD Radeon RX 7900 XTX
7550,	C3,	AMD Radeon RX 9070
7550,	C0,	AMD Radeon RX 9070 XT  \r
7551,	C0,	Radeon Without Prefix
7552,	C0,
"""
IDS = {(0x73BF, 0xC0): "Radeon RX 6900 XT", (0x73BF, 0xC1): "Radeon RX 6800 XT",
       (0x744C, 0xC8): "Radeon RX 7900 XTX", (0x7550, 0xC3): "Radeon RX 9070",
       (0x7550, 0xC0): "Radeon RX 9070 XT", (0x7551, 0xC0): "Radeon Without Prefix"}

failures = []


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}{'' if cond else ': ' + detail}")
    if not cond:
        failures.append(name)


# ---------- fake sysfs tree ----------

def snapshot(root):
    dev = f"{root}/bus/pci/devices/{PCI}"
    for f in DEVICE_FILES:
        os.makedirs(os.path.dirname(f"{dev}/{f}"), exist_ok=True)
        with open(f"{REAL_DEV}/{f}", "rb") as src, open(f"{dev}/{f}", "wb") as dst:
            dst.write(src.read())
    real_hwmon = glob.glob(f"{REAL_DEV}/hwmon/hwmon*")[0]
    hwmon = f"{dev}/hwmon/{os.path.basename(real_hwmon)}"
    os.makedirs(hwmon)
    for f in sorted(os.listdir(real_hwmon)):
        if f.startswith(HWMON_PREFIXES) and os.path.isfile(f"{real_hwmon}/{f}"):
            try:
                data = open(f"{real_hwmon}/{f}", "rb").read()
            except OSError:
                continue
            open(f"{hwmon}/{f}", "wb").write(data)
    drv = f"{root}/bus/pci/drivers/amdgpu"
    os.makedirs(drv)
    os.symlink(f"../../devices/{PCI}", f"{drv}/{PCI}")
    for f in ("bind", "unbind", "new_id", "remove_id", "uevent"):
        open(f"{drv}/{f}", "w").close()
    os.makedirs(f"{root}/module/amdgpu")
    os.symlink("../../../module/amdgpu", f"{drv}/module")


def set_gc(dev, major, minor, revision):
    for name, value in (("major", major), ("minor", minor), ("revision", revision)):
        write(f"{dev}/{GC_DIR}/{name}", f"{value}\n")


def hwmon_dir(dev):
    found = glob.glob(f"{dev}/hwmon/hwmon*")
    return found[0] if found else None


def write(path, text):
    with open(path, "w") as f:
        f.write(text)


# ---------- expected values, computed independently from the tree ----------

def expected(root, pci=PCI):
    dev = f"{root}/bus/pci/devices/{pci}"

    def num(path):
        try:
            return int(open(path).read().strip())
        except (OSError, ValueError):
            return None

    def scaled(path, div):
        v = num(path)
        return None if v is None else v / div

    hw = hwmon_dir(dev)
    temp_idx, freq_idx = {}, {}
    if hw:
        for i in range(1, 9):
            for kind, idx in (("temp", temp_idx), ("freq", freq_idx)):
                try:
                    idx[open(f"{hw}/{kind}{i}_label").read().strip()] = i
                except OSError:
                    pass

    def hwval(kind, idx, label, item, div):
        if not hw or label not in idx:
            return None
        return scaled(f"{hw}/{kind}{idx[label]}_{item}", div)

    def dpm_max(name):
        try:
            levels = [float(line.split(":")[1].strip().split("M")[0])
                      for line in open(f"{dev}/{name}") if ":" in line]
        except OSError:
            levels = []
        return max(levels) if levels else None

    def hexfile(name):
        try:
            return int(open(f"{dev}/{name}").read().strip(), 16)
        except (OSError, ValueError):
            return 0

    chip, seed = CHIPS[tuple(num(f"{dev}/{GC_DIR}/{f}") for f in ("major", "minor", "revision"))]
    awake_seed = seed if seed is not None else dpm_max("pp_dpm_sclk")
    vram_total = scaled(f"{dev}/mem_info_vram_total", 1024)
    e = {
        "status": "active", "pci": pci,
        "card": IDS.get((hexfile("device"), hexfile("revision")), f"Radeon {chip}"),
        "vramTotal": vram_total, "mclkMax": dpm_max("pp_dpm_mclk"),
        "tempCrit": [hwval("temp", temp_idx, lbl, "crit", 1000) for lbl in LABELS],
        "temp": [None] * 3, "sclkPeak": awake_seed,
        "fanMax": scaled(f"{hw}/fan1_max", 1) if hw else None,
    }
    for k in DYNAMIC:
        e[k] = None
    try:
        status = open(f"{dev}/power/runtime_status").read().strip()
    except OSError:
        status = None
    if status == "suspended":
        # nothing is read from a sleeping card, not even the values that never change
        e.update(status="suspended", vramTotal=None, mclkMax=None, tempCrit=[None] * 3, fanMax=None,
                 sclkPeak=seed)
        return e

    e["gpuBusy"] = num(f"{dev}/gpu_busy_percent")
    e["memBusy"] = num(f"{dev}/mem_busy_percent")
    e["vcnBusy"] = num(f"{dev}/vcn_busy_percent")
    e["vramUsed"] = scaled(f"{dev}/mem_info_vram_used", 1024)
    if hw:
        e["power"] = scaled(f"{hw}/power1_average", 1e6)
        if e["power"] is None:
            e["power"] = scaled(f"{hw}/power1_input", 1e6)
        e["powerCap"] = scaled(f"{hw}/power1_cap", 1e6)
        e["fan"] = num(f"{hw}/fan1_input")
    e["temp"] = [hwval("temp", temp_idx, lbl, "input", 1000) for lbl in LABELS]
    e["sclk"] = hwval("freq", freq_idx, "sclk", "input", 1e6)
    e["mclk"] = hwval("freq", freq_idx, "mclk", "input", 1e6)
    if e["sclk"] is not None:
        e["sclkPeak"] = e["sclk"] if awake_seed is None else max(awake_seed, e["sclk"])
    if e["mclk"] is not None:
        e["memRate"] = e["mclk"] * MEM_RATE_MULTIPLIER / 1000
    try:
        m = gpu_metrics.read(f"{dev}/gpu_metrics")
        if (m["structure_size"], m["format_revision"], m["content_revision"]) == (120, 1, 3):
            e["vclk"] = None if m["current_vclk0"] == 0xFFFF else m["current_vclk0"]
            e["dclk"] = None if m["current_dclk0"] == 0xFFFF else m["current_dclk0"]
            # only a card without the file (RDNA 2) takes the video engine load from gpu_metrics
            if not os.path.lexists(f"{dev}/vcn_busy_percent"):
                e["vcnBusy"] = None if m["average_mm_activity"] == 0xFFFF else m["average_mm_activity"]
    except Exception:  # missing, truncated or unparsable table
        pass
    return e


def not_found():
    e = {"status": "not_found", "card": None, "pci": None, "vramTotal": None, "mclkMax": None,
         "tempCrit": [None] * 3, "temp": [None] * 3, "sclkPeak": None, "fanMax": None}
    for k in DYNAMIC:
        e[k] = None
    return e


def same(a, b):
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))
    return a == b


def diff(got, want):
    keys = sorted(set(got) | set(want))
    return {k: (got.get(k), want.get(k)) for k in keys if not same(got.get(k), want.get(k))}


def valid_idle_sclk(sample):
    # The driver's averaged gfx clock can report zero at idle (AUDIT.md finding 5).
    clock, peak = sample["sclk"], sample["sclkPeak"]
    return clock is not None and peak is not None and 0 <= clock <= peak and peak >= SCLK_SEED


# ---------- driver process ----------

class Sampler:
    def __init__(self, binary):
        self.p = subprocess.Popen([binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True)

    def sample(self, ms):
        self.p.stdin.write(f"{ms}\n")
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())

    def close(self):
        self.p.stdin.close()
        err = self.p.stderr.read()
        rc = self.p.wait()
        return rc, err


def run_case(name, binary, root, base, mutate, want_fn):
    print(f"[{name}]")
    shutil.rmtree(root, ignore_errors=True)
    shutil.copytree(base, root, symlinks=True)
    mutate(root)
    want = want_fn(root)
    s = Sampler(binary)
    got = s.sample(1)
    rc, err = s.close()
    d = diff(got, want)
    check("values", not d, json.dumps(d))
    check("clean exit (ASan/UBSan)", rc == 0 and not err.strip(), f"rc={rc} {err.strip()[:400]}")
    return got


def main():
    tmp = tempfile.mkdtemp(prefix="htop-gpu-test-")
    try:
        base, root = f"{tmp}/base", f"{tmp}/root"
        live_bin, fake_bin = f"{tmp}/sample-live", f"{tmp}/sample-fake"
        build = os.path.join(HERE, "build-sampler.sh")
        subprocess.run([build, live_bin, "/sys"], check=True)
        write(f"{tmp}/amdgpu.ids", IDS_TEXT)
        subprocess.run([build, fake_bin, root, f"{tmp}/amdgpu.ids"], check=True)
        snapshot(base)

        def dev(r):
            return f"{r}/bus/pci/devices/{PCI}"

        # ----- 1. snapshot -----
        run_case("snapshot: exact match", fake_bin, root, base, lambda r: None, expected)

        # ----- 2. faults -----
        def hw(r):
            return hwmon_dir(dev(r))

        def metrics_patch(offset, data):
            def f(r):
                path = f"{dev(r)}/gpu_metrics"
                raw = bytearray(open(path, "rb").read())
                raw[offset:offset + len(data)] = data
                open(path, "wb").write(bytes(raw))
            return f

        def swap_temp(r):
            h = hw(r)
            for item in ("label", "input", "crit"):
                a, b = f"{h}/temp1_{item}", f"{h}/temp3_{item}"
                os.rename(a, a + ".x")
                os.rename(b, a)
                os.rename(a + ".x", b)

        def power_input(r):
            h = hw(r)
            os.rename(f"{h}/power1_average", f"{h}/power1_input")

        def two_cards(r):
            drv = f"{r}/bus/pci/drivers/amdgpu"
            # 02:00.0 is integrated graphics (an APU's graphics core), 03:00.0 a second dedicated card
            for addr, devid, gc, busy in (("0000:03:00.0", "0x7550", (12, 0, 1), "77"),
                                          ("0000:02:00.0", "0x1681", (10, 3, 6), "66")):
                shutil.copytree(dev(r), f"{r}/bus/pci/devices/{addr}", symlinks=True)
                write(f"{r}/bus/pci/devices/{addr}/device", devid + "\n")
                write(f"{r}/bus/pci/devices/{addr}/gpu_busy_percent", busy + "\n")
                set_gc(f"{r}/bus/pci/devices/{addr}", *gc)
                os.symlink(f"../../devices/{addr}", f"{drv}/{addr}")

        def other_card(devid, revision, gc, sclk_levels, vcn_file=True, mm_activity=None):
            def f(r):
                write(f"{dev(r)}/device", devid + "\n")
                write(f"{dev(r)}/revision", revision + "\n")
                set_gc(dev(r), *gc)
                if sclk_levels is None:
                    os.remove(f"{dev(r)}/pp_dpm_sclk")
                else:
                    write(f"{dev(r)}/pp_dpm_sclk",
                          "".join(f"{i}: {mhz}Mhz {'*' if i == 0 else ''}\n" for i, mhz in enumerate(sclk_levels)))
                if not vcn_file:
                    os.remove(f"{dev(r)}/vcn_busy_percent")
                if mm_activity is not None:
                    metrics_patch(20, mm_activity)(r)
            return f

        rdna2 = other_card("0x73bf", "0xc1", (10, 3, 0), [500, 2575], vcn_file=False, mm_activity=b"\x25\x00")

        cases = [
            ("suspended card: nothing read",
             lambda r: write(f"{dev(r)}/power/runtime_status", "suspended\n"), expected),
            ("no runtime_status file: treated as active",
             lambda r: os.remove(f"{dev(r)}/power/runtime_status"), expected),
            ("gpu_metrics revision 1.4: vclk/dclk N/A", metrics_patch(3, b"\x04"), expected),
            ("gpu_metrics wrong size field: vclk/dclk N/A", metrics_patch(0, b"\x80\x00"), expected),
            ("gpu_metrics truncated", lambda r: os.truncate(f"{dev(r)}/gpu_metrics", 60), expected),
            ("gpu_metrics clocks unset (0xFFFF)", metrics_patch(60, b"\xff\xff\xff\xff"), expected),
            ("temp labels swapped: mapped by label", swap_temp, expected),
            ("mem temp input missing", lambda r: os.remove(f"{hw(r)}/temp3_input"), expected),
            ("garbage in gpu_busy_percent", lambda r: write(f"{dev(r)}/gpu_busy_percent", "abc\n"), expected),
            ("power1_average missing: falls back to power1_input", power_input, expected),
            ("no hwmon dir", lambda r: shutil.rmtree(f"{dev(r)}/hwmon"), expected),
            ("empty pp_dpm_mclk", lambda r: write(f"{dev(r)}/pp_dpm_mclk", ""), expected),
            ("fan spinning", lambda r: write(f"{hw(r)}/fan1_input", "1193\n"), expected),
            ("fan1_input missing", lambda r: os.remove(f"{hw(r)}/fan1_input"), expected),
            ("fan1_max missing", lambda r: os.remove(f"{hw(r)}/fan1_max"), expected),
            ("lowest dedicated card's PCI address wins, integrated graphics skipped",
             two_cards, lambda r: expected(r, "0000:03:00.0")),
            ("RDNA 2 (RX 6800 XT): video load from gpu_metrics, clock bar from pp_dpm_sclk", rdna2, expected),
            ("RDNA 2: video load unset in gpu_metrics",
             other_card("0x73bf", "0xc0", (10, 3, 0), [500, 2575], vcn_file=False, mm_activity=b"\xff\xff"), expected),
            ("RDNA 2: gpu_metrics of another revision, no video load",
             lambda r: (rdna2(r), metrics_patch(3, b"\x04")(r)), expected),
            ("RDNA 3 (RX 7900 XTX)", other_card("0x744c", "0xc8", (11, 0, 0), [500, 2695]), expected),
            ("RDNA 4 (RX 9060 XT) without a name in amdgpu.ids: named after the chip",
             other_card("0x7590", "0xc0", (12, 0, 0), [500, 2400]), expected),
            ("no pp_dpm_sclk: clock bar starts at the first clock read",
             other_card("0x744c", "0xc8", (11, 0, 0), None), expected),
            ("garbage in vcn_busy_percent: no fallback to gpu_metrics",
             lambda r: write(f"{dev(r)}/vcn_busy_percent", "abc\n"), expected),
            ("other revision of the device: its own name",
             lambda r: write(f"{dev(r)}/revision", "0xc3\n"), expected),
            ("unknown revision: named after the chip", lambda r: write(f"{dev(r)}/revision", "0xff\n"), expected),
            ("no revision file: named after the chip", lambda r: os.remove(f"{dev(r)}/revision"), expected),
            ("amdgpu.ids name without the AMD prefix", lambda r: write(f"{dev(r)}/device", "0x7551\n"), expected),
            ("amdgpu.ids line with an empty name: named after the chip",
             lambda r: write(f"{dev(r)}/device", "0x7552\n"), expected),
            ("integrated graphics (APU graphics core)", lambda r: set_gc(dev(r), 10, 3, 6), lambda r: not_found()),
            ("RDNA 1 graphics core", lambda r: set_gc(dev(r), 10, 1, 10), lambda r: not_found()),
            ("unknown graphics core", lambda r: set_gc(dev(r), 13, 0, 0), lambda r: not_found()),
            ("garbage graphics core version",
             lambda r: write(f"{dev(r)}/{GC_DIR}/minor", "abc\n"), lambda r: not_found()),
            ("no ip_discovery", lambda r: shutil.rmtree(f"{dev(r)}/ip_discovery"), lambda r: not_found()),
            ("non-AMD vendor", lambda r: write(f"{dev(r)}/vendor", "0x1022\n"), lambda r: not_found()),
            ("not bound to amdgpu",
             lambda r: os.remove(f"{r}/bus/pci/drivers/amdgpu/{PCI}"), lambda r: not_found()),
            ("no amdgpu driver dir",
             lambda r: shutil.rmtree(f"{r}/bus/pci/drivers"), lambda r: not_found()),
        ]
        for name, mutate, want in cases:
            run_case(name, fake_bin, root, base, mutate, want)

        print("[idle GPU clock: zero, positive, then zero under one running sampler]")
        shutil.rmtree(root, ignore_errors=True)
        shutil.copytree(base, root, symlinks=True)
        clock = f"{hw(root)}/freq1_input"
        s = Sampler(fake_bin)
        for ms, hz in ((100, 0), (200, 1500000000), (300, 0)):
            write(clock, f"{hz}\n")
            got = s.sample(ms)
            d = diff(got, expected(root))
            check(f"{hz} Hz sample values", not d, json.dumps(d))
            check(f"{hz} Hz passes idle plausibility", valid_idle_sclk(got), json.dumps(got))
        rc, err = s.close()
        check("clean exit (ASan/UBSan)", rc == 0 and not err.strip(), err.strip()[:400])

        print("[idle GPU clock: invalid readings are still rejected]")
        for name, clock, peak in (("missing clock", None, SCLK_SEED),
                                  ("negative clock", -1, SCLK_SEED),
                                  ("clock above peak", SCLK_SEED + 1, SCLK_SEED),
                                  ("missing peak", 0, None),
                                  ("peak below seed", 0, SCLK_SEED - 1)):
            check(name, not valid_idle_sclk({"sclk": clock, "sclkPeak": peak}))

        # ----- 3. cache -----
        print("[cache: same or older monotonicMs never re-reads]")
        shutil.rmtree(root, ignore_errors=True)
        shutil.copytree(base, root, symlinks=True)
        busy = f"{dev(root)}/gpu_busy_percent"
        write(busy, "11\n")
        s = Sampler(fake_bin)
        check("first sample reads", s.sample(100)["gpuBusy"] == 11)
        write(busy, "22\n")
        check("same ms keeps cached value", s.sample(100)["gpuBusy"] == 11)
        check("newer ms re-reads", s.sample(200)["gpuBusy"] == 22)
        write(busy, "33\n")
        check("older ms keeps cached value", s.sample(150)["gpuBusy"] == 22)
        check("newer ms re-reads again", s.sample(300)["gpuBusy"] == 33)
        rc, err = s.close()
        check("clean exit (ASan/UBSan)", rc == 0 and not err.strip(), err.strip()[:400])

        print("[wake up: a card that starts suspended gets its static values once awake]")
        status = f"{dev(root)}/power/runtime_status"
        write(status, "suspended\n")
        s = Sampler(fake_bin)
        first = s.sample(100)
        check("starts suspended with nothing read",
              first["status"] == "suspended" and first["vramTotal"] is None and first["tempCrit"] == [None] * 3)
        write(status, "active\n")
        d = diff(s.sample(200), expected(root))
        check("full sample after waking", not d, json.dumps(d))
        rc, err = s.close()
        check("clean exit (ASan/UBSan)", rc == 0 and not err.strip(), err.strip()[:400])

        # ----- recovery: the tree changes under ONE running sampler (AUDIT.md finding 2) -----
        def recovery(name, before, change, want_before, after=None, want_after=expected):
            print(f"[recovery: {name}]")
            shutil.rmtree(root, ignore_errors=True)
            shutil.copytree(base, root, symlinks=True)
            if before:
                before(root)
            s = Sampler(fake_bin)
            d = diff(s.sample(100), want_before(root))
            check("first sample", not d, json.dumps(d))
            change(root)
            d = diff(s.sample(200), want_after(root))
            check("after the change", not d, json.dumps(d))
            if after:
                after(root)
                d = diff(s.sample(300), expected(root))
                check("after changing back", not d, json.dumps(d))
            rc, err = s.close()
            check("clean exit (ASan/UBSan)", rc == 0 and not err.strip(), err.strip()[:400])

        def hide_hwmon(r):
            os.rename(f"{dev(r)}/hwmon", f"{r}/hwmon.hidden")

        def restore_hwmon(r):
            os.rename(f"{r}/hwmon.hidden", f"{dev(r)}/hwmon")

        def renumber_hwmon(r):
            h = hwmon_dir(dev(r))
            os.rename(h, os.path.join(os.path.dirname(h), "hwmon99"))

        link = f"bus/pci/drivers/amdgpu/{PCI}"

        def unbind(r):
            os.remove(f"{r}/{link}")

        def rebind(r):
            os.symlink(f"../../devices/{PCI}", f"{r}/{link}")

        recovery("hwmon missing at start, appears later", hide_hwmon, restore_hwmon, expected)
        recovery("hwmon renumbered while running", None, renumber_hwmon, expected)
        recovery("card bound only after start", unbind, rebind, lambda r: not_found())
        recovery("card unbound while running, then bound again", None, unbind, expected,
                 after=rebind, want_after=lambda r: not_found())

        # Each value read only once must be read again if it failed at first (AUDIT.md finding 4)
        def hide(rel):
            def f(r):
                path = glob.glob(f"{dev(r)}/{rel}")[0]
                os.rename(path, f"{r}/hidden")
                open(f"{r}/hidden.path", "w").write(path)
            return f

        def unhide(r):
            os.rename(f"{r}/hidden", open(f"{r}/hidden.path").read())

        def fan_spinning(r):
            write(f"{hw(r)}/fan1_input", "1193\n")

        for rel in ("hwmon/*/fan1_max", "mem_info_vram_total", "pp_dpm_mclk", "hwmon/*/temp2_crit",
                    "hwmon/*/temp3_label", "hwmon/*/freq1_label", "hwmon/*/freq2_label"):
            recovery(f"{rel} missing at start, appears later",
                     lambda r, rel=rel: (fan_spinning(r), hide(rel)(r)), unhide, expected)

        # A value the card does not have (file absent) stops being looked for; one that fails
        # to read (file there, no number) never does
        print("[absent or failed: fan1_max under one running sampler]")
        shutil.rmtree(root, ignore_errors=True)
        shutil.copytree(base, root, symlinks=True)
        fan_max = f"{hw(root)}/fan1_max"
        real_max = open(fan_max).read()
        write(fan_max, "abc\n")
        s = Sampler(fake_bin)
        d = [diff(s.sample(ms), expected(root)) for ms in range(100, 100 * (ABSENT_TRIES + 6), 100)]
        check("garbage: N/A, everything else read", not any(d), json.dumps(d))
        write(fan_max, real_max)
        ms = 100 * (ABSENT_TRIES + 6)
        d = diff(s.sample(ms), expected(root))
        check(f"garbage fixed after {ABSENT_TRIES + 5} refreshes: read", not d, json.dumps(d))
        os.remove(fan_max)
        renumber_hwmon(root)
        fan_max = f"{hw(root)}/fan1_max"
        for i in range(ABSENT_TRIES - 1):
            ms += 100
            d = diff(s.sample(ms), expected(root))
            check(f"absent, refresh {i + 1}: N/A, everything else read", not d, json.dumps(d))
        write(fan_max, real_max)
        ms += 100
        d = diff(s.sample(ms), expected(root))
        check(f"appears on refresh {ABSENT_TRIES}: read", not d, json.dumps(d))
        os.remove(fan_max)
        renumber_hwmon2 = os.path.join(os.path.dirname(hw(root)), "hwmon98")
        os.rename(hw(root), renumber_hwmon2)
        fan_max = f"{renumber_hwmon2}/fan1_max"
        for i in range(ABSENT_TRIES + 3):
            ms += 100
            d = diff(s.sample(ms), expected(root))
            check(f"absent again, refresh {i + 1}: N/A, everything else read", not d, json.dumps(d))
        write(fan_max, real_max)
        write(f"{dev(root)}/gpu_busy_percent", "42\n")
        ms += 100
        want = expected(root)
        want["fanMax"] = None
        got = s.sample(ms)
        d = diff(got, want)
        check(f"appears after {ABSENT_TRIES} refreshes: no longer looked for, the rest still live",
              not d and got["gpuBusy"] == 42, json.dumps(d))
        os.rename(renumber_hwmon2, os.path.join(os.path.dirname(renumber_hwmon2), "hwmon97"))
        ms += 100
        d = diff(s.sample(ms), expected(root))
        check("hwmon renumbered: looked for again and read", not d, json.dumps(d))
        rc, err = s.close()
        check("clean exit (ASan/UBSan)", rc == 0 and not err.strip(), err.strip()[:400])

        print("[RDNA 2 under one running sampler: clock bar grows from pp_dpm_sclk, video load follows gpu_metrics]")
        shutil.rmtree(root, ignore_errors=True)
        shutil.copytree(base, root, symlinks=True)
        rdna2(root)
        clock = f"{hw(root)}/freq1_input"
        s = Sampler(fake_bin)
        peak = 2575.0
        for ms, mhz, activity in ((100, 600, 0), (200, 2700, 81), (300, 900, 12)):
            write(clock, f"{mhz * 1000000}\n")
            metrics_patch(20, bytes([activity, 0]))(root)
            peak = max(peak, mhz)
            got = s.sample(ms)
            want = expected(root)
            want["sclkPeak"] = peak
            d = diff(got, want)
            check(f"{mhz} MHz, video {activity}%: peak {peak:g} MHz", not d and got["vcnBusy"] == activity,
                  json.dumps(d))
        write(f"{dev(root)}/vcn_busy_percent", "55\n")
        got = s.sample(400)
        check("vcn_busy_percent appears: used instead", got["vcnBusy"] == 55, json.dumps(got))
        rc, err = s.close()
        check("clean exit (ASan/UBSan)", rc == 0 and not err.strip(), err.strip()[:400])

        # ----- 4. live -----
        print("[live /sys: idle plausibility]")
        s = Sampler(live_bin)
        t0 = time.monotonic()
        idle = []
        for _ in range(5):
            idle.append(s.sample(int((time.monotonic() - t0) * 1000) + 1))
            time.sleep(0.3)
        for x in idle:
            problems = []
            if x["status"] != "active" or x["card"] != "Radeon RX 9070 XT" or x["pci"] != PCI:
                problems.append("identity")
            for k in ("gpuBusy", "memBusy", "vcnBusy"):
                if x[k] is None or not 0 <= x[k] <= 100:
                    problems.append(k)
            if x["vramUsed"] is None or not 0 < x["vramUsed"] < x["vramTotal"]:
                problems.append("vram")
            if x["power"] is None or not 1 < x["power"] < x["powerCap"] * 1.2:
                problems.append("power")
            if any(t is None or not 15 < t < 105 for t in x["temp"]):
                problems.append("temp")
            if not valid_idle_sclk(x):
                problems.append("sclk")
            if x["mclk"] is None or not 0 < x["mclk"] <= x["mclkMax"] + 1:
                problems.append("mclk")
            if not same(x["memRate"], x["mclk"] * MEM_RATE_MULTIPLIER / 1000):
                problems.append("memRate")
            if x["fan"] is None or x["fanMax"] is None or not 0 <= x["fan"] <= x["fanMax"] * 1.2:
                problems.append("fan")
            if x["vclk"] is None or x["dclk"] is None:
                problems.append("vclk/dclk")
            check(f"sample busy={x['gpuBusy']}% {x['power']}W sclk={x['sclk']} mclk={x['mclk']} "
                  f"temps={x['temp']} vram={x['vramUsed'] / 1048576:.2f}G", not problems, ",".join(problems))

        if shutil.which("ffmpeg") and os.path.exists(RENDER):
            print("[live /sys: VA-API H.264 encode on the 9070 XT]")
            cmd = ["ffmpeg", "-nostdin", "-v", "error", "-vaapi_device", RENDER, "-f", "lavfi",
                   "-i", "testsrc2=size=1920x1080:rate=60", "-t", "30", "-vf", "format=nv12,hwupload",
                   "-c:v", "h264_vaapi", "-qp", "24", "-f", "null", "-"]
            ff = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            load = []
            while ff.poll() is None:
                load.append(s.sample(int((time.monotonic() - t0) * 1000) + 1))
                time.sleep(0.3)
            ff_err = ff.stderr.read()
            check("ffmpeg ran", ff.returncode == 0, ff_err.strip()[:300])
            vcn = max((x["vcnBusy"] or 0) for x in load) if load else 0
            vclk = max((x["vclk"] or 0) for x in load) if load else 0
            dclk = max((x["dclk"] or 0) for x in load) if load else 0
            check(f"video engine busy peaked at {vcn}% ({len(load)} samples)", vcn >= 50)
            check(f"vclk peaked at {vclk} MHz, dclk at {dclk} MHz", vclk >= 1000 and dclk >= 1000)
        else:
            print("[live VA-API load skipped: no ffmpeg or render node]")

        rc, err = s.close()
        check("live clean exit (ASan/UBSan)", rc == 0 and not err.strip(), err.strip()[:400])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{'ALL PASSED' if not failures else f'{len(failures)} FAILED: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
