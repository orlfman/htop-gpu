#!/usr/bin/env python3
"""Tests for src/htop/linux/IntelRAPL.c and the full htop package power meter.

1. fake powercap trees, changed under ONE running sampler: power from energy deltas, counter
   wrap-around, a replaced counter, cache, several packages, subzones ignored, each package
   counted once from its MSR or MMIO interface, no access, counters appearing / disappearing,
   long term limits changing / failing / recovering
2. the terminal decoder shared with htop-capture.py, on a value getting shorter and longer
3. the full htop meter against a fake AMD package in a PTY, including the pause key (Z)
4. live: the real /sys at idle, then with every CPU busy (omit with --fake-only)

Needs src/htop configured (./configure). Run: python3 -I test-rapl.py
"""
import argparse, fcntl, json, math, os, pty, re, runpy, select, shutil, signal, struct, subprocess, sys, tempfile, termios, time
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src", "htop")
RANGE = 262143328850
failures = []
decode_screen = runpy.run_path(f"{HERE}/htop-capture.py")["decode_screen"]


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}{'' if cond else ': ' + detail}")
    if not cond:
        failures.append(name)


def build(out, root, source=None):
    subprocess.run(["gcc", "-std=c99", "-Wall", "-Wextra", "-Wshadow", "-Wformat-nonliteral", "-Werror",
                    "-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    f"-I{SRC}", f"-I{SRC}/linux", f'-DINTELRAPL_SYSFS_ROOT="{root}"',
                    f"{HERE}/rapl-sample.c", str(source or f"{SRC}/linux/IntelRAPL.c"), f"{SRC}/linux/Compat.c",
                    f"{SRC}/XUtils.c", "-lm", "-o", out], check=True)


def write(path, text):
    with open(path, "w") as f:
        f.write(text)


def zone(root, name, kind, energy, limit_uw=250000000, rng=RANGE):
    d = f"{root}/class/powercap/{name}"
    os.makedirs(d, exist_ok=True)
    write(f"{d}/name", kind + "\n")
    write(f"{d}/energy_uj", f"{energy}\n")
    write(f"{d}/max_energy_range_uj", f"{rng}\n")
    if limit_uw is not None:
        write(f"{d}/constraint_0_name", "long_term\n")
        write(f"{d}/constraint_0_power_limit_uw", f"{limit_uw}\n")
        write(f"{d}/constraint_1_name", "short_term\n")
        write(f"{d}/constraint_1_power_limit_uw", f"{limit_uw}\n")
    return d


def energy(d, uj):
    write(f"{d}/energy_uj", f"{uj}\n")


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
        return self.p.wait(), err


def near(a, b):
    return a is not None and abs(a - b) < 1e-9 * max(1.0, abs(b))


def scenario(name, binary, root, steps):
    """steps: list of (ms, change(root) or None, expectation(sample) -> (ok, detail))"""
    print(f"[{name}]")
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    s = Sampler(binary)
    for ms, change, want, label in steps:
        if change:
            change(root)
        got = s.sample(ms)
        check(label, want(got), json.dumps(got))
    rc, err = s.close()
    check("clean exit (ASan/UBSan)", rc == 0 and not err.strip(), f"rc={rc} {err.strip()[:400]}")


def is_(status, power="any", limit="any", packages=None):
    def f(x):
        if x["status"] != status:
            return False
        if power != "any" and not (x["power"] is None if power is None else near(x["power"], power)):
            return False
        if limit != "any" and not (x["powerLimit"] is None if limit is None else near(x["powerLimit"], limit)):
            return False
        return packages is None or x["packages"] == packages
    return f



def live_packages():
    """Package zones straight from sysfs, independent of the sampler: {name: [msr dir, mmio dir]}."""
    packages = {}
    for zone_path in sorted(Path("/sys/class/powercap").glob("intel-rapl*:*")):
        if zone_path.name.count(":") != 1:
            continue
        try:
            name = (zone_path / "name").read_text().strip()
        except OSError:
            continue
        if name.startswith("package-"):
            packages.setdefault(name, [None, None])[1 if "mmio" in zone_path.name else 0] = zone_path
    return packages


def live_readable_counters():
    """Package counters a normal user can read now, whatever the sampler under test says."""
    readable = []
    for dirs in live_packages().values():
        for zone_path in dirs:
            try:
                if zone_path is not None:
                    readable.append((zone_path.name, int((zone_path / "energy_uj").read_text())))
                    break
            except (OSError, ValueError):
                continue
    return readable


def live_limits():
    """Determine PL1 independently, preferring a positive MSR limit per package."""
    limits = []
    for dirs in live_packages().values():
        limit = 0
        for zone_path in filter(None, dirs):
            try:
                files = list(zone_path.glob("constraint_*_name"))
                limit = next((int((zone_path / f"{f.name[:-5]}_power_limit_uw").read_text())
                              for f in files if f.read_text().strip() == "long_term"), 0)
            except (OSError, ValueError):
                limit = 0
            if limit > 0:
                break
        limits.append(limit)
    return sum(limits) / 1e6 if limits and all(value > 0 for value in limits) else None


def live_test(tmp):
    print("[live /sys: idle, then all CPUs busy]")
    binary = f"{tmp}/rapl-live"
    build(binary, "/sys")
    s = Sampler(binary)
    t0 = time.monotonic()
    ms = lambda: int((time.monotonic() - t0) * 1000) + 1
    try:
        first = s.sample(ms())
        readable = live_readable_counters()
        if first["status"] != "active":
            # Only skip when sysfs itself has nothing readable, never on the sampler's word alone.
            if readable:
                check("sampler finds the readable live package counters", False,
                      f"sysfs has {readable} but the sampler says {json.dumps(first)}")
            else:
                print(f"  SKIP live watts: no readable package counter in sysfs ({first['status']})")
            return
        check(f"sampler counts every live package ({len(live_packages())})",
              first["packages"] == len(live_packages()), json.dumps(first))

        expected_limit = live_limits()
        check(f"long term limit matches sysfs ({expected_limit} W)",
              is_("active", limit=expected_limit)(first), json.dumps(first))
        time.sleep(1.5)
        idle = s.sample(ms())
        check(f"idle power {idle['power']} W is finite and nonnegative",
              idle["power"] is not None and math.isfinite(idle["power"]) and idle["power"] >= 0,
              json.dumps(idle))
        burners = []
        try:
            for _ in range(len(os.sched_getaffinity(0))):
                burners.append(subprocess.Popen([sys.executable, "-I", "-c", "while True: pass"]))
            time.sleep(1.0)
            s.sample(ms())
            time.sleep(2.0)
            busy = s.sample(ms())
        finally:
            for b in burners:
                b.kill()
            for b in burners:
                b.wait()
        check(f"busy power {busy['power']} W above idle {idle['power']} W",
              busy["power"] is not None and idle["power"] is not None and busy["power"] > idle["power"],
              json.dumps(busy))
        rc_path = f"{tmp}/live.htoprc"
        meter_config(rc_path)
        capture = subprocess.check_output(
            [sys.executable, "-I", f"{HERE}/htop-capture.py", rc_path, f"{SRC}/htop", "2"], text=True)
        text = re.search(r"Pwr:\d+\.\dW[^\n]*", capture)
        want = f"limit:{expected_limit:.0f}W" if expected_limit is not None else None
        check("live htop displays watts and the optional limit",
              text and (want in text.group() if want else "limit:" not in text.group()), capture[:500])
    finally:
        rc, err = s.close()
        check("live clean exit (ASan/UBSan)", rc == 0 and not err.strip(), err.strip()[:400])


def decoder_test():
    """ncurses shortens "10.6W" to "9.6W" by deleting a character, and lengthens it by inserting one."""
    print("[terminal decoder: values getting shorter and longer]")
    csi = "\x1b["
    start = f"{csi}1;1H{csi}36mPwr{csi}0m{csi}1m:10.6W{csi}0m{csi}36m limit{csi}0m"
    shorter = start + f"{csi}1;5H{csi}1P{csi}1m9{csi}0m"
    longer = shorter + f"{csi}1;5H{csi}1@{csi}1m10{csi}0m"

    def row(raw):
        cells = decode_screen(raw.encode(), 2, 40)[0]
        text = "".join(ch for ch, _ in cells).rstrip()
        runs = []
        for ch, attr in cells[:len(text)]:
            if runs and runs[-1][0] == attr:
                runs[-1][1] += ch
            else:
                runs.append([attr, ch])
        return text, [tuple(r) for r in runs]

    check("delete-character shortens 10.6W to 9.6W, colors intact", row(shorter) ==
          ("Pwr:9.6W limit", [("cyan", "Pwr"), ("bold", ":9.6W"), ("cyan", " limit")]), repr(row(shorter)))
    check("insert-character lengthens 9.6W back to 10.6W, colors intact", row(longer) ==
          ("Pwr:10.6W limit", [("cyan", "Pwr"), ("bold", ":10.6W"), ("cyan", " limit")]), repr(row(longer)))


def meter_config(rc):
    write(rc, "config_reader_min_version=3\nheader_layout=one_100\nheader_margin=0\ndelay=2\n"
              "column_meters_0=IntelCPUInfo IntelCPUPower IntelCPUPower IntelCPUPower IntelCPUPower IntelCPUInfo\n"
              "column_meter_modes_0=2 2 1 3 4 2\n")


class HtopSession:
    def __init__(self, binary, rc, cols, env):
        self.rows, self.cols = (88 if cols == 200 else 40), cols
        self.raw = bytearray()
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            try:
                fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack("HHHH", self.rows, cols, 0, 0))
                os.execve(binary, [binary], dict(env, TERM="xterm-256color", HTOPRC=rc))
            finally:
                os._exit(127)

    def until(self, predicate, tick=lambda: None, timeout=4):
        deadline = time.monotonic() + timeout
        lines = []
        while time.monotonic() < deadline:
            tick()
            if not select.select([self.fd], [], [], 0.02)[0]:
                continue
            try:
                data = os.read(self.fd, 65536)
            except OSError:
                break
            self.raw.extend(data)
            lines = ["".join(ch for ch, _ in row).strip()
                     for row in decode_screen(self.raw, self.rows, self.cols)]
            if predicate(lines):
                return True, lines
        return False, lines

    def close(self):
        try:
            os.write(self.fd, b"q")
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                pid, status = os.waitpid(self.pid, os.WNOHANG)
                if pid:
                    return os.waitstatus_to_exitcode(status)
                if select.select([self.fd], [], [], 0.05)[0]:
                    try:
                        os.read(self.fd, 65536)
                    except OSError:
                        time.sleep(0.05)
        except OSError:
            pass
        finally:
            os.close(self.fd)
        os.kill(self.pid, signal.SIGTERM)
        return os.waitstatus_to_exitcode(os.waitpid(self.pid, 0)[1])


def meter_test(tmp, binary, root, cols):
    model = "AMD Ryzen 9 7950X"
    rc = f"{tmp}/amd-{cols}.htoprc"
    meter_config(rc)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    logs = f"{tmp}/logs"
    os.makedirs(logs, exist_ok=True)
    env = dict(os.environ, ASAN_OPTIONS=f"log_path={logs}/asan:detect_leaks=0",
               UBSAN_OPTIONS=f"log_path={logs}/ubsan:print_stacktrace=1")
    session = HtopSession(binary, rc, cols, env)

    def expect(label, predicate, tick=lambda: None):
        ok, lines = session.until(predicate, tick)
        check(f"{cols} columns, {label}", ok, repr(lines[:15]))

    try:
        expect("no AMD package yet", lambda s: "Pwr:N/A" in s and s.count(model) == 2)
        package = zone(root, "intel-rapl:0", "package-0", 1000000, limit_uw=None)
        limit_name = f"{package}/constraint_0_name"
        limit_path = f"{package}/constraint_0_power_limit_uw"
        feed = {"since": time.monotonic(), "base": 1000000, "rate": 42_500_000}

        def fed():
            return int((time.monotonic() - feed["since"]) * feed["rate"]) + feed["base"]

        def set_rate(uw):
            feed.update(base=fed(), since=time.monotonic(), rate=uw)

        def tick():
            # Atomic replacement lets htop see a complete integer while we feed the running counter.
            write(f"{package}/next", f"{fed()}\n")
            os.replace(f"{package}/next", f"{package}/energy_uj")

        def reading(line, prefix, low=34, high=51):
            match = re.match(re.escape(prefix) + r"\s*(\d+\.\d)W", line)
            return match and low <= float(match[1]) <= high

        def watts_only(s):
            # Graph preserves four rows, LED three. The final heading fixes the layout height.
            return (len(s) > 10 and s[0] == s[10] == model and
                    reading(s[1], "Pwr:") and reading(s[2], "Pwr[") and reading(s[3], "Pwr:") and
                    s[2].endswith("W]") and "|" not in s[2] and not any(s[4:7]) and
                    any("W" in row for row in s[7:10]) and
                    not any("limit:" in row for row in s[:10]))

        def limited(s, limit):
            return (len(s) > 10 and s[0] == s[10] == model and reading(s[1], "Pwr:") and
                    s[1].endswith(f" limit:{limit}W") and s[2].endswith(f"/{limit}W]") and
                    "|" in s[2] and s[3] == "Pwr" and any(s[4:7]) and
                    any("limit:" in row for row in s[7:10]))

        expect("watts only in text, bar, graph and LED", watts_only, tick)
        if cols == 200:
            # Pausing freezes the process list, not the header: the meter must follow a new rate.
            # Only the wide layout shows "PAUSED" in the function bar to prove the pause took effect.
            os.write(session.fd, b"Z")
            set_rate(12_000_000)
            expect("package watts keep updating while paused (Z)", lambda s:
                   any("PAUSED" in row for row in s) and len(s) > 1 and reading(s[1], "Pwr:", 9, 15), tick)
            os.write(session.fd, b"Z")
            set_rate(42_500_000)
            expect("watts follow the counter again after resuming", lambda s:
                   not any("PAUSED" in row for row in s) and watts_only(s), tick)
        write(limit_name, "long_term\n")
        write(limit_path, "250000000\n")
        expect("250 W limit fills bar and restores chart", lambda s: limited(s, 250), tick)
        os.unlink(limit_path)
        expect("removed limit restores watts-only mode", watts_only, tick)
        write(limit_path, "65000000\n")
        expect("65 W limit resumes plotting", lambda s: limited(s, 65), tick)
        write(limit_path, "0\n")
        expect("zero limit leaves watts visible", watts_only, tick)
        write(limit_path, "65000000\n")
        expect("valid limit restores plot again", lambda s: limited(s, 65), tick)
        write(limit_path, "65junk\n")
        expect("invalid limit restores watts-only mode", watts_only, tick)
        write(limit_path, "65000000\n")
        expect("valid PL1 before permission loss", lambda s: limited(s, 65), tick)
        os.chmod(f"{package}/energy_uj", 0)
        expect("energy permissions shown even with PL1", lambda s: "Pwr:no access" in s and
               sum("no access" in row for row in s[:10]) == 4)
        os.unlink(limit_path)
        os.chmod(f"{package}/energy_uj", 0o644)
        expect("genuine zero after permissions recover", lambda s: s.count("Pwr:0.0W") == 2)
        shutil.rmtree(package)
        expect("removed package shows N/A again", lambda s: s.count("Pwr:N/A") == 3)
        if cols == 200:
            os.write(session.fd, b"\x1bOQ")
            expect("F2 opens Setup", lambda s: any("Display options" in row for row in s))
            os.write(session.fd, b"\x1bOB\x1bOB")
            expect("Setup offers each CPU meter once, with vendor-neutral names", lambda s:
                   sum("CPU package power (RAPL)" in row for row in s) == 1 and
                   sum("CPU model name, as a heading" in row for row in s) == 1 and
                   sum("CPU package power [" in row for row in s) == 4 and
                   sum("CPU heading [Text]" in row for row in s) == 2 and
                   not any("Intel CPU" in row for row in s))
            os.write(session.fd, b"\x1b[21~")
            expect("F10 returns to the process list", lambda s:
                   any(row.startswith("PID USER") for row in s) and
                   not any("Available meters" in row for row in s))
    finally:
        status = session.close()
        check(f"{cols} columns, htop exits cleanly", status == 0, f"exit {status}")
    reports = os.listdir(logs)
    check("no full htop ASan/UBSan reports", not reports, " ".join(reports))


def full_meter_tests(tmp, root):
    binary, cpuinfo = f"{tmp}/htop-rapl", f"{tmp}/cpuinfo"
    write(cpuinfo, "model name\t: AMD Ryzen 9 7950X\n")
    flags = f'-DINTELRAPL_SYSFS_ROOT=\\"{root}\\" -DPROCCPUINFOFILE=\\"{cpuinfo}\\"'
    subprocess.run([f"{HERE}/build-htop-asan.sh", binary, "", flags], check=True)
    print("[full htop: fake AMD powercap through all meter modes]", flush=True)
    for cols in (200, 48):
        meter_test(tmp, binary, root, cols)


def counter_replacement_during_read(tmp, root):
    # Replace the zone just after its identity check. Keep the old directory readable
    # so a pinned read can finish this interval before re-baselining on the new zone.
    live = Path(root) / "class/powercap/intel-rapl:0"
    old = live.with_name("old")
    new = live.with_name("replacement")
    source = Path(tmp) / "rapl-replacement.c"
    original = (Path(SRC) / "linux/IntelRAPL.c").read_text()
    injection = f"""
#include <stdio.h>
#include <sys/stat.h>

static int afterIdentityCheck(int result) {{
   static unsigned int calls;
   if (result == 0 && ++calls == 2) {{
      if (rename("{live}", "{old}") || rename("{new}", "{live}"))
         abort();
   }}
   return result;
}}

#define stat(path, st) afterIdentityCheck(stat(path, st))
#define fstat(fd, st) afterIdentityCheck(fstat(fd, st))

"""
    marker = "#ifndef INTELRAPL_SYSFS_ROOT"
    source.write_text(original.replace(marker, injection + marker, 1))
    binary = f"{tmp}/rapl-replacement"
    build(binary, root, source)

    def initial(r):
        zone(r, "intel-rapl:0", "package-0", 50000000)
        zone(r, "replacement", "package-0", 1000000)

    scenario("zone changes between its identity check and energy read", binary, root, [
        (100, initial, is_("active", None, 250, 1), "old zone baseline at 50 J"),
        (1100, lambda r: energy(live, 55000000), is_("active", 5, 250, 1),
         "pinned read finishes with 5 W from the old zone"),
        (2100, None, is_("active", None, 250, 1), "new zone starts from its own baseline"),
        (3100, lambda r: energy(live, 3000000), is_("active", 2, 250, 1),
         "new zone reports 2 W"),
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fake-only", action="store_true", help="skip live hardware tests")
    args = parser.parse_args()
    tmp = tempfile.mkdtemp(prefix="htop-gpu-rapl-")
    try:
        root = f"{tmp}/root"
        fake = f"{tmp}/rapl-fake"
        build(fake, root)
        pk = lambda r: f"{r}/class/powercap/intel-rapl:0"

        def one_package(r):
            zone(r, "intel-rapl:0", "package-0", 1000000)
            # must be ignored: a subzone and the MMIO copy of the same package
            zone(r, "intel-rapl:0:0", "core", 5)
            zone(r, "intel-rapl-mmio:0", "package-0", 7, limit_uw=None)

        scenario("power from energy deltas, cache, wrap-around", fake, root, [
            (100, one_package, is_("active", None, 250, 1), "first sample: no power yet, limit 250 W, 1 package"),
            (1100, lambda r: energy(pk(r), 62000000), is_("active", 61.0, 250, 1), "61 J in 1 s = 61.0 W"),
            (1100, lambda r: energy(pk(r), 99000000), is_("active", 61.0), "same timestamp keeps the cached value"),
            (900, None, is_("active", 61.0), "older timestamp keeps the cached value"),
            (1600, lambda r: energy(pk(r), 99000000), is_("active", 74.0), "37 J in 0.5 s = 74.0 W"),
            (2600, lambda r: energy(pk(r), RANGE - 1000000), is_("active", (RANGE - 1000000 - 99000000) / 1e6), "big step"),
            (3600, lambda r: energy(pk(r), 2000000), is_("active", 3.0), "counter wrapped: 3 J in 1 s = 3.0 W"),
        ])

        def two_packages(r):
            zone(r, "intel-rapl:0", "package-0", 0)
            zone(r, "intel-rapl:1", "package-1", 0, limit_uw=125000000)

        def both(uj0, uj1):
            def f(r):
                energy(f"{r}/class/powercap/intel-rapl:0", uj0)
                energy(f"{r}/class/powercap/intel-rapl:1", uj1)
            return f

        scenario("two packages are summed", fake, root, [
            (100, two_packages, is_("active", None, 375, 2), "2 packages, limits 250 + 125 W"),
            (1100, both(40000000, 20000000), is_("active", 60.0, 375, 2), "40 + 20 J in 1 s = 60.0 W"),
        ])

        def amd_packages(r):
            zone(r, "intel-rapl:0", "package-0", 1000000, limit_uw=None)
            zone(r, "intel-rapl:1", "package-1", 2000000, limit_uw=125000000)
            zone(r, "intel-rapl:0:0", "core", 5)
            zone(r, "intel-rapl-mmio:0", "package-0", 7, limit_uw=None)

        scenario("AMD-shaped packages and optional PL1", fake, root, [
            (100, amd_packages, is_("active", None, None, 2), "one missing limit means no combined limit"),
            (1100, both(11000000, 22000000), is_("active", 30, None, 2), "both packages, core and MMIO omitted"),
            (2100, None, is_("active", 0, None, 2), "unchanged counters report zero"),
            (3100, lambda r: (both(21000000, 42000000)(r), write(f"{pk(r)}/constraint_0_name", "long_term\n"),
                             write(f"{pk(r)}/constraint_0_power_limit_uw", "0\n")),
             is_("active", 30, None, 2), "one zero limit means no combined limit"),
            (4100, lambda r: (os.chmod(f"{r}/class/powercap/intel-rapl:1/energy_uj", 0),
                             energy(pk(r), 31000000)),
             is_("no_access", None, None, 2), "one denied package invalidates aggregate watts"),
        ])

        scenario("fractional watts with no constraint files", fake, root, [
            (100, lambda r: zone(r, "intel-rapl:0", "package-0", 1000000, limit_uw=None),
             is_("active", None, None, 1), "initial sample establishes baseline"),
            (350, lambda r: energy(pk(r), 11625000),
             is_("active", 42.5, None, 1), "10.625 J in 250 ms = 42.5 W without PL1"),
        ])

        def deny(r):
            os.chmod(f"{pk(r)}/energy_uj", 0)

        def allow(r):
            os.chmod(f"{pk(r)}/energy_uj", 0o644)

        def msr_only(r):
            zone(r, "intel-rapl:0", "package-0", 1000000)
            zone(r, "intel-rapl:0:0", "core", 5)

        scenario("counter not readable, then readable", fake, root, [
            (100, lambda r: (msr_only(r), deny(r)), is_("no_access", None), "root-only counter: no_access"),
            (1100, None, is_("no_access", None), "still no_access"),
            (2100, lambda r: (allow(r), energy(pk(r), 5000000)), is_("active", None), "readable: starts over"),
            (3100, lambda r: energy(pk(r), 15000000), is_("active", 10.0), "10 J in 1 s = 10.0 W"),
        ])

        scenario("counters appear after start, disappear, come back", fake, root, [
            (100, None, is_("not_found", None, None, 0), "no powercap dir: not_found"),
            (1100, one_package, is_("active", None, 250, 1), "zone appears: found again"),
            (2100, lambda r: energy(pk(r), 21000000), is_("active", 20.0), "20 J in 1 s = 20.0 W"),
            (3100, lambda r: shutil.rmtree(f"{r}/class"), is_("not_found", None, None, 0), "zone gone: not_found"),
            (4100, one_package, is_("active", None, 250, 1), "zone back: found again"),
        ])

        def no_limit(r):
            one_package(r)
            os.rename(f"{pk(r)}/constraint_0_power_limit_uw", f"{r}/limit.hidden")

        scenario("long term limit missing at start, appears later", fake, root, [
            (100, no_limit, is_("active", None, None), "limit missing"),
            (1100, lambda r: (energy(pk(r), 11000000), os.rename(f"{r}/limit.hidden", f"{pk(r)}/constraint_0_power_limit_uw")),
             is_("active", 10.0, 250), "limit read again: 250 W"),
        ])

        def power_and_limit(r, uj, limit_uw):
            energy(pk(r), uj)
            path = f"{pk(r)}/constraint_0_power_limit_uw"
            if limit_uw is None:
                os.unlink(path)
            else:
                write(path, f"{limit_uw}\n")

        scenario("long term limit changes, fails, and recovers without restarting", fake, root, [
            (100, one_package, is_("active", None, 250, 1), "initial limit: 250 W"),
            (1100, lambda r: energy(pk(r), 62000000), is_("active", 61.0, 250), "61 W against 250 W"),
            (1100, lambda r: power_and_limit(r, 123000000, 65000000),
             is_("active", 61.0, 250), "same timestamp caches energy and limit"),
            (900, None, is_("active", 61.0, 250), "older timestamp caches energy and limit"),
            (2100, None, is_("active", 61.0, 65), "newer timestamp reads changed 65 W limit"),
            (3100, lambda r: power_and_limit(r, 184000000, None),
             is_("active", 61.0, None), "removed limit becomes unavailable, watts stay valid"),
            (3100, lambda r: power_and_limit(r, 245000000, 125000000),
             is_("active", 61.0, None), "same timestamp keeps unavailable limit cached"),
            (4100, None, is_("active", 61.0, 125), "limit restored: 125 W"),
            (5100, lambda r: power_and_limit(r, 306000000, "junk"),
             is_("active", 61.0, None), "malformed limit becomes unavailable"),
            (6100, lambda r: power_and_limit(r, 367000000, 65000000),
             is_("active", 61.0, 65), "valid limit recovers after malformed value"),
            (7100, lambda r: (energy(pk(r), 428000000), os.chmod(f"{pk(r)}/constraint_0_power_limit_uw", 0)),
             is_("active", 61.0, None), "unreadable limit becomes unavailable"),
            (8100, lambda r: (os.chmod(f"{pk(r)}/constraint_0_power_limit_uw", 0o644), power_and_limit(r, 489000000, 250000000)),
             is_("active", 61.0, 250), "readable limit recovers: 250 W"),
        ])

        def no_range(r):
            one_package(r)
            energy(pk(r), RANGE - 1000000)
            os.unlink(f"{pk(r)}/max_energy_range_uj")

        scenario("counter range missing at start, restored before wrap", fake, root, [
            (100, no_range, is_("active", None, 250), "first sample without a counter range"),
            (1100, lambda r: (write(f"{pk(r)}/max_energy_range_uj", f"{RANGE}\n"), energy(pk(r), 2000000)),
             is_("active", 3.0, 250), "range retried: wrapped delta is 3 W"),
        ])

        scenario("counter decreases without a wrap range", fake, root, [
            (100, no_range, is_("active", None, 250), "first sample without a counter range"),
            (1100, lambda r: energy(pk(r), 2000000), is_("active", None, 250), "wrap interval is unavailable"),
            (2100, lambda r: energy(pk(r), 4500000), is_("active", 2.5, 250), "next interval uses the new baseline"),
        ])

        scenario("garbage counter", fake, root, [
            (100, lambda r: (msr_only(r), energy(pk(r), "junk")), is_("not_found", None), "unparsable: forgotten"),
            (1100, lambda r: energy(pk(r), 1000000), is_("active", None, 250), "valid again: found again"),
        ])

        def replace_package(r, uj):
            # Built next to the old zone and swapped in, so it is a different directory at the same path.
            new = zone(r, "intel-rapl:0.new", "package-0", uj)
            os.rename(pk(r), f"{r}/class/powercap/old")
            os.rename(new, pk(r))
            shutil.rmtree(f"{r}/class/powercap/old")

        scenario("replaced package counter starts over", fake, root, [
            (100, lambda r: zone(r, "intel-rapl:0", "package-0", 50000000), is_("active", None, 250, 1), "baseline at 50 J"),
            (1100, lambda r: replace_package(r, 1000000), is_("active", None, 250, 1),
             "replacement at 1 J is a new baseline, not a 262 kW wrap"),
            (2100, lambda r: energy(pk(r), 3000000), is_("active", 2.0, 250, 1), "2 J in 1 s = 2.0 W from the new counter"),
            (3100, lambda r: energy(pk(r), 1000000), is_("active", (RANGE - 2000000) / 1e6, 250, 1),
             "a genuine wrap of the same counter still counts"),
        ])

        mm = lambda r: f"{r}/class/powercap/intel-rapl-mmio:0"

        scenario("MMIO interface by itself", fake, root, [
            (100, lambda r: zone(r, "intel-rapl-mmio:0", "package-0", 1000000), is_("active", None, 250, 1),
             "MMIO-only package is found"),
            (1100, lambda r: energy(mm(r), 21000000), is_("active", 20.0, 250, 1), "MMIO counter supplies 20 W"),
        ])

        scenario("both interfaces count the package once", fake, root, [
            (100, one_package, is_("active", None, 250, 1), "MSR and MMIO views are one package"),
            (1100, lambda r: (energy(pk(r), 11000000), energy(mm(r), 999000000)), is_("active", 10.0, 250, 1),
             "the MSR counter supplies 10 W, MMIO is not added"),
        ])

        def both_views(r):
            zone(r, "intel-rapl:0", "package-0", 1000000)
            zone(r, "intel-rapl-mmio:0", "package-0", 5000000, limit_uw=65000000)

        scenario("unreadable MSR falls back to readable MMIO", fake, root, [
            (100, lambda r: (both_views(r), deny(r)), is_("active", None, 250, 1),
             "denied MSR counter: MMIO supplies the package, PL1 still from MSR"),
            (1100, lambda r: energy(mm(r), 20000000), is_("active", 15.0, 250, 1), "MMIO supplies 15 W"),
            (2100, lambda r: (allow(r), energy(pk(r), 30000000), energy(mm(r), 40000000)), is_("active", None, 250, 1),
             "MSR readable again: the source changes and starts over"),
            (3100, lambda r: (energy(pk(r), 42000000), energy(mm(r), 99000000)), is_("active", 12.0, 250, 1),
             "MSR supplies 12 W again"),
            (4100, lambda r: (deny(r), os.chmod(f"{mm(r)}/energy_uj", 0)), is_("no_access", None),
             "both interfaces denied: no access"),
        ])

        scenario("MMIO supplies PL1 when the MSR limit is unavailable", fake, root, [
            (100, both_views, is_("active", None, 250, 1), "prefer the valid 250 W MSR limit"),
            (1100, lambda r: (power_and_limit(r, 11000000, None), energy(mm(r), 25000000)),
             is_("active", 10, 65, 1), "MSR energy and MMIO limit are independent"),
            (2100, lambda r: (shutil.rmtree(pk(r)), energy(mm(r), 45000000)),
             is_("active", None, 65, 1), "removing MSR re-baselines energy and keeps the MMIO limit"),
            (3100, lambda r: energy(mm(r), 65000000), is_("active", 20, 65, 1),
             "MMIO supplies 20 W against its 65 W limit"),
        ])

        def other_mm(r):
            return f"{r}/class/powercap/intel-rapl-mmio:1"

        def remap_msr(r):
            shutil.rmtree(pk(r))
            zone(r, "intel-rapl:0", "package-1", 2000000, limit_uw=125000000)
            energy(mm(r), 15000000)
            energy(other_mm(r), 45000000)

        scenario("MSR path reused for a different package", fake, root, [
            (100, lambda r: (both_views(r), zone(r, "intel-rapl-mmio:1", "package-1", 5000000)),
             is_("active", None, 500, 2), "package 0 on MSR, package 1 on MMIO"),
            (1100, remap_msr, is_("active", None, 190, 2),
             "package name changed, regroup and start both baselines again"),
            (2100, lambda r: (energy(mm(r), 25000000), energy(other_mm(r), 85000000), energy(pk(r), 42000000)),
             is_("active", 50, 190, 2), "10 W from package 0 and 40 W from package 1"),
        ])

        counter_replacement_during_read(tmp, root)
        decoder_test()
        full_meter_tests(tmp, root)
        if not args.fake_only:
            live_test(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{'ALL PASSED' if not failures else f'{len(failures)} FAILED: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
