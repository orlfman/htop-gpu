#!/usr/bin/env python3
"""Tests for src/htop/linux/IntelRAPL.c (Intel CPU package power) through the rapl-sample driver.

1. fake powercap trees, changed under ONE running sampler: power from energy deltas, counter
   wrap-around, cache, several packages, subzones and intel-rapl-mmio ignored, no access,
   counters appearing / disappearing, long term limits changing / failing / recovering
2. live: the real /sys at idle, then with every CPU busy

Needs src/htop configured (./configure). Run: python3 -I test-rapl.py
"""
import json, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src", "htop")
RANGE = 262143328850
failures = []


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}{'' if cond else ': ' + detail}")
    if not cond:
        failures.append(name)


def build(out, root):
    subprocess.run(["gcc", "-std=c99", "-Wall", "-Wextra", "-Wshadow", "-Wformat-nonliteral", "-Werror",
                    "-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    f"-I{SRC}", f"-I{SRC}/linux", f'-DINTELRAPL_SYSFS_ROOT="{root}"',
                    f"{HERE}/rapl-sample.c", f"{SRC}/linux/IntelRAPL.c", f"{SRC}/linux/Compat.c",
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


def main():
    tmp = tempfile.mkdtemp(prefix="htop-gpu-rapl-")
    try:
        root = f"{tmp}/root"
        fake, live = f"{tmp}/rapl-fake", f"{tmp}/rapl-live"
        build(fake, root)
        build(live, "/sys")
        pk = lambda r: f"{r}/class/powercap/intel-rapl:0"

        def one_package(r):
            zone(r, "intel-rapl:0", "package-0", 1000000)
            # must be ignored: a subzone and the MMIO copy of the same package
            zone(r, "intel-rapl:0:0", "core", 5)
            zone(r, "intel-rapl-mmio:0", "package-0", 7)

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

        def deny(r):
            os.chmod(f"{pk(r)}/energy_uj", 0)

        def allow(r):
            os.chmod(f"{pk(r)}/energy_uj", 0o644)

        scenario("counter not readable, then readable", fake, root, [
            (100, lambda r: (one_package(r), deny(r)), is_("no_access", None), "root-only counter: no_access"),
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

        scenario("garbage counter", fake, root, [
            (100, lambda r: (one_package(r), energy(pk(r), "junk")), is_("not_found", None), "unparsable: forgotten"),
            (1100, lambda r: energy(pk(r), 1000000), is_("active", None, 250), "valid again: found again"),
        ])

        print("[live /sys: idle, then all CPUs busy]")
        s = Sampler(live)
        t0 = time.monotonic()
        ms = lambda: int((time.monotonic() - t0) * 1000) + 1
        first = s.sample(ms())
        check("package found", first["status"] == "active" and first["packages"] >= 1, json.dumps(first))
        check("long term limit 1..1000 W", first["powerLimit"] is not None and 1 <= first["powerLimit"] <= 1000, json.dumps(first))
        time.sleep(1.5)
        idle = s.sample(ms())
        check(f"idle power {idle['power']} W plausible (0.5..400 W)", idle["power"] is not None and 0.5 <= idle["power"] <= 400, json.dumps(idle))
        burners = [subprocess.Popen([sys.executable, "-I", "-c", "while True: pass"]) for _ in range(os.cpu_count())]
        try:
            time.sleep(1.0)
            s.sample(ms())
            time.sleep(2.0)
            busy = s.sample(ms())
        finally:
            for b in burners:
                b.kill()
        check(f"busy power {busy['power']} W above idle {idle['power']} W", busy["power"] is not None and idle["power"] is not None
              and busy["power"] > idle["power"] + 5, json.dumps(busy))
        rc, err = s.close()
        check("live clean exit (ASan/UBSan)", rc == 0 and not err.strip(), err.strip()[:400])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{'ALL PASSED' if not failures else f'{len(failures)} FAILED: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
