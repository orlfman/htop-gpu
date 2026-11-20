#!/usr/bin/env python3
"""Tests for the heading meters: IntelCPUInfo (linux/IntelRAPLMeter.c) and AMDGPUInfo (linux/AMDGPUMeter.c).

Runs the real dev htop in a pty (htop-capture.py) with only the two headings in the header.
1. CPU name: a fake cpuinfo per case ((R)/(TM) in any case, " @ GHz", spacing, length, missing)
2. AMD heading: the fake card (fake-sysfs.py) changes state under ONE running htop
3. pause: the AMD GPU usage meter keeps following the fake card while the process list is
   paused (Z), as the header does (linux/MeterClock.h, shared by the GPU and CPU power meters)
4. live: the normal dev binary shows this machine's CPU and card names

The heading sources (and linux/AMDGPU.c) are rebuilt with a fake cpuinfo / sysfs root and
ASan + UBSan, then rebuilt normally. Needs src/htop configured (./configure) and the 9070 XT
(fake-sysfs.py copies its files). Run: python3 -I test-headings.py
"""
import os, re, runpy, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "src", "htop"))
SOURCES = ["linux/AMDGPU.c", "linux/AMDGPUMeter.c", "linux/IntelRAPLMeter.c", "linux/IntelGPUMeter.c"]
SANITIZE = "-fsanitize=address,undefined -fno-omit-frame-pointer"
CARD = "Radeon RX 9070 XT"
failures = []


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}{'' if cond else ': ' + detail}")
    if not cond:
        failures.append(name)


def make(*args):
    subprocess.run(["make", "-C", SRC, "-s", f"-j{os.cpu_count()}", *args, "htop"], check=True)


def touch_sources():
    for f in SOURCES:
        os.utime(os.path.join(SRC, f))


def build(out, cpuinfo, sysfs):
    # everything else up to date first, so the fake paths and sanitizers only reach SOURCES
    make()
    try:
        touch_sources()
        make(f'CPPFLAGS=-DPROCCPUINFOFILE=\\"{cpuinfo}\\" -DAMDGPU_SYSFS_ROOT=\\"{sysfs}\\"',
             f"CFLAGS=-g -O1 {SANITIZE}", f"LDFLAGS={SANITIZE}")
        shutil.copy(os.path.join(SRC, "htop"), out)
    finally:
        touch_sources()
        make()


def write(path, text):
    with open(path, "w") as f:
        f.write(text)


def htoprc(path):
    write(path, "config_reader_min_version=3\nheader_layout=one_100\ndelay=5\n"
                "column_meters_0=IntelCPUInfo AMDGPUInfo\ncolumn_meter_modes_0=2 2\n")


def fake_card(root, *state):
    subprocess.run([sys.executable, "-I", f"{HERE}/fake-sysfs.py", root, *state],
                   check=True, stdout=subprocess.DEVNULL)


def headings(rc, binary, seconds, during=None):
    """The two header rows as (text, colors) after `seconds`; `during` runs halfway through"""
    htoprc(rc)
    # These assertions expect color even if the caller disables it for regular use.
    env = os.environ.copy()
    env.pop("NO_COLOR", None)
    p = subprocess.Popen([sys.executable, "-I", f"{HERE}/htop-capture.py", rc, binary, str(seconds)],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    if during:
        time.sleep(seconds / 2)
        during()
    lines = p.communicate()[0].splitlines()
    rows = [(lines[i].strip(), lines[i + 1].strip()) for i in range(0, len(lines) - 1, 2)]
    return rows[:2] + [("", "")] * (2 - len(rows[:2]))


def clean(model):
    """Reference for the C cleanup: the expected heading for a cpuinfo model name"""
    model = re.sub(r"\((R|TM)\)", "", model, flags=re.IGNORECASE).split(" @ ")[0]
    return " ".join(model.split())[:63].rstrip() or "CPU"


CPU_CASES = [
    ("Arrow Lake", "model name\t: Intel(R) Core(TM) Ultra 7 270K Plus\n", "Intel Core Ultra 7 270K Plus"),
    ("@ GHz cut", "model name\t: Intel(R) Core(TM) i7-8700K CPU @ 3.70GHz\n", "Intel Core i7-8700K CPU"),
    ("tabs and repeated spaces", "model name\t: \t Intel(R)   Xeon(R) CPU E5-2680 v4 @ 2.40GHz  \n",
     "Intel Xeon CPU E5-2680 v4"),
    ("lowercase (tm)", "model name\t: AMD Athlon(tm) II X4 640 Processor\n", "AMD Athlon II X4 640 Processor"),
    ("lowercase (r)", "model name\t: Intel(r) Pentium(r) 4 CPU 3.00GHz\n", "Intel Pentium 4 CPU 3.00GHz"),
    ("no marks", "model name\t: AMD Ryzen 9 7950X 16-Core Processor\n", "AMD Ryzen 9 7950X 16-Core Processor"),
    ("first model name wins", "processor\t: 0\nmodel name\t: First CPU\n\nprocessor\t: 1\nmodel name\t: Second CPU\n",
     "First CPU"),
    ("only marks: fallback", "model name\t: (R)(TM)\n", "CPU"),
    ("empty name: fallback", "model name\t: \n", "CPU"),
    ("no model name line: fallback", "processor\t: 0\nvendor_id\t: GenuineIntel\n", "CPU"),
    ("empty file: fallback", "", "CPU"),
    ("missing file: fallback", None, "CPU"),
    ("cut at 63 characters", f"model name\t: {'A' * 40} {'B' * 40}\n", f"{'A' * 40} {'B' * 22}"),
    ("no space left for the next word", f"model name\t: {'A' * 62} BBB\n", "A" * 62),
]

AMD_CASES = [
    # (name, state at start, state switched to while htop runs, expected heading)
    ("active -> suspended", [], ["--suspended"], f"{CARD}: sleep"),
    ("active -> unbound", [], ["--unbind"], "AMD GPU: N/A"),
    ("unbound -> active (rediscovered)", ["--unbind"], [], CARD),
    ("suspended -> active", ["--suspended"], [], CARD),
    ("suspended at start", ["--suspended"], None, f"{CARD}: sleep"),
    ("active -> power state unknown", [], ["--write", "power/runtime_status=error"], f"{CARD}: N/A"),
    ("power state unknown -> active", ["--write", "power/runtime_status=error"], [], CARD),
    ("unbound at start", ["--unbind"], None, "AMD GPU: N/A"),
]


def pause_test(binary, sysfs, tmp):
    """htop freezes the process list on Z but keeps updating the header; so must the GPU meters."""
    print("[AMD GPU usage while the process list is paused (Z)]")
    HtopSession = runpy.run_path(f"{HERE}/test-rapl.py")["HtopSession"]
    rc = f"{tmp}/pause.htoprc"
    write(rc, "config_reader_min_version=3\nheader_layout=one_100\ndelay=2\n"
              "column_meters_0=AMDGPUUsage\ncolumn_meter_modes_0=1\n")
    fake_card(sysfs, "--write", "gpu_busy_percent=11")
    usage = lambda rows, value: any(re.match(rf"GPU\[.*\b{value}%\]", row) for row in rows)
    paused = lambda rows: any("PAUSED" in row for row in rows)
    session = HtopSession(binary, rc, 200, dict(os.environ))
    try:
        ok, rows = session.until(lambda s: usage(s, 11))
        check("usage before the pause: 11%", ok, repr(rows[:3]))
        os.write(session.fd, b"Z")
        ok, rows = session.until(paused)
        check("Z pauses the process list", ok, repr(rows[-3:]))
        fake_card(sysfs, "--write", "gpu_busy_percent=77")
        ok, rows = session.until(lambda s: paused(s) and usage(s, 77))
        check("usage follows the card to 77% while paused", ok, repr(rows[:3]))
        os.write(session.fd, b"Z")
        fake_card(sysfs, "--write", "gpu_busy_percent=33")
        ok, rows = session.until(lambda s: not paused(s) and usage(s, 33))
        check("usage follows the card to 33% after resuming", ok, repr(rows[:3]))
    finally:
        status = session.close()
    check("pause test htop exits cleanly", status == 0, f"exit {status}")
    fake_card(sysfs)


def main():
    tmp = tempfile.mkdtemp(prefix="htop-headings-")
    try:
        cpuinfo, sysfs, logs = f"{tmp}/cpuinfo", f"{tmp}/sysfs", f"{tmp}/logs"
        binary, rc = f"{tmp}/htop-headings", f"{tmp}/htoprc"
        os.makedirs(logs)
        os.environ["ASAN_OPTIONS"] = f"log_path={logs}/asan:detect_leaks=0"
        os.environ["UBSAN_OPTIONS"] = f"log_path={logs}/ubsan:print_stacktrace=1"
        fake_card(sysfs)
        build(binary, cpuinfo, sysfs)

        print("[CPU heading: fake cpuinfo]")
        for name, text, want in CPU_CASES:
            if text is None:
                if os.path.exists(cpuinfo):
                    os.remove(cpuinfo)
            else:
                write(cpuinfo, text)
            (cpu, colors), (amd, _) = headings(rc, binary, 1.5)
            check(f"{name}: {want!r}", cpu == want and colors == f"[cyan]{want}", f"got {cpu!r} {colors!r}")
            if name == "Arrow Lake":
                check(f"AMD heading next to it: {CARD!r}", amd == CARD, f"got {amd!r}")

        print("[AMD heading: card state changes under one running htop]")
        write(cpuinfo, CPU_CASES[0][1])
        for name, start, switch, want in AMD_CASES:
            fake_card(sysfs, *start)
            during = None if switch is None else (lambda s=switch: fake_card(sysfs, *s))
            _, (amd, colors) = headings(rc, binary, 4 if during else 1.5, during)
            check(f"{name}: {want!r}", amd == want and colors == f"[cyan]{want}", f"got {amd!r} {colors!r}")

        pause_test(binary, sysfs, tmp)

        print("[sanitizers]")
        reports = os.listdir(logs)
        check("no ASan/UBSan reports", not reports, " ".join(reports))

        print("[live: normal dev binary]")
        with open("/proc/cpuinfo") as f:
            model = next((l.split(":", 1)[1] for l in f if l.startswith("model name")), "")
        (cpu, _), (amd, _) = headings(rc, os.path.join(SRC, "htop"), 2)
        check(f"CPU heading {clean(model)!r}", cpu == clean(model), f"got {cpu!r}")
        check(f"AMD heading {CARD!r}", amd == CARD, f"got {amd!r}")
        with open(os.path.join(SRC, "htop"), "rb") as f:
            data = f.read()
        check("normal binary has no fake paths or sanitizers",
              tmp.encode() not in data and b"__asan_init" not in data, "rebuild src/htop")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{'ALL PASSED' if not failures else f'{len(failures)} FAILED: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
