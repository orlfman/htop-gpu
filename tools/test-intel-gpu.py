#!/usr/bin/env python3
"""Stateful Intel iGPU tests. No real configs, permissions, or packages are changed.

Run python3 -I tools/test-intel-gpu.py [--fake-only] [--mutations].
Fake fd links use /dev/null, whose device number is advertised by the fake DRM nodes.
Live tests pin Intel VA-API/Vulkan and keep temporary media inside the test directory.
"""
import argparse
import contextlib
import io
import json
import math
import os
from pathlib import Path
import select
import shutil
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src/htop"
PCI = "0000:00:02.0"
failures = []


def check(label, good, detail=""):
    print(f"  {'ok  ' if good else 'FAIL'} {label}" + ("" if good else f": {detail}"), flush=True)
    if not good:
        failures.append(label)


def build(binary, sysroot, procroot, source=None):
    subprocess.run(["gcc", "-std=c99", "-Wall", "-Wextra", "-Wshadow", "-Wformat-nonliteral", "-Werror",
                    "-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    f"-I{SRC}", f"-I{SRC}/linux", f'-DINTELGPU_SYSFS_ROOT="{sysroot}"',
                    f'-DINTELGPU_PROC_ROOT="{procroot}"', str(HERE / "intel-gpu-sample.c"),
                    str(source or SRC / "linux/IntelGPU.c"), str(SRC / "linux/Compat.c"),
                    str(SRC / "XUtils.c"), "-lm", "-o", str(binary)], check=True)


class Sampler:
    def __init__(self, binary):
        self.p = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True)

    def sample(self, ms):
        self.p.stdin.write(f"{ms}\n")
        self.p.stdin.flush()
        if not select.select([self.p.stdout], [], [], 4)[0]:
            self.p.kill()
            raise RuntimeError("sampler timed out (possibly read hardware while suspended)")
        text = self.p.stdout.readline()
        if not text:
            raise RuntimeError(f"sampler stopped: {self.p.stderr.read()}")
        return json.loads(text)

    def close(self):
        if self.p.poll() is None:
            self.p.stdin.close()
        err = self.p.stderr.read()
        return self.p.wait(timeout=5), err


class Tree:
    def __init__(self, root):
        self.root = Path(root)
        self.sys = self.root / "sys"
        self.proc = self.root / "proc"
        self.card = "card7"

    def reset(self):
        shutil.rmtree(self.root, ignore_errors=True)
        self.sys.mkdir(parents=True)
        self.proc.mkdir()
        self.card = "card7"

    @property
    def dev(self):
        return self.sys / "bus/pci/devices" / PCI

    @property
    def gt(self):
        return self.dev / "drm" / self.card / "gt/gt0"

    def write(self, path, value):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(value) + "\n")

    def bind(self):
        link = self.sys / "bus/pci/drivers/i915" / PCI
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(self.dev)

    def device(self):
        self.write(self.dev / "vendor", "0x8086")
        self.write(self.dev / "device", "0x7d67")
        self.write(self.dev / "power/runtime_status", "active")
        for node in (self.card, "renderD333"):
            self.write(self.dev / "drm" / node / "dev", "1:3")
        self.write(self.gt / "rps_cur_freq_mhz", 550)
        self.write(self.gt / "rps_act_freq_mhz", 750)
        self.write(self.gt / "rps_max_freq_mhz", 2000)
        self.bind()

    def process(self, pid=100, starttime=1000):
        # starttime is field 22; comm deliberately contains spaces and parentheses.
        fields = [str(pid), "(gpu (test) app)", "S", *(["0"] * 18), str(starttime), "0"]
        self.write(self.proc / str(pid) / "stat", " ".join(fields))

    def client(self, pid=100, fd=3, cid=1, render=0, compute=0, video=0,
               memory="1024 KiB", capacity=2, pci=PCI, driver="i915", target="/dev/null", omit=()):
        path = self.proc / str(pid)
        if not (path / "stat").exists():
            self.process(pid)
        (path / "fd").mkdir(parents=True, exist_ok=True)
        (path / "fdinfo").mkdir(exist_ok=True)
        link = path / "fd" / str(fd)
        link.unlink(missing_ok=True)
        link.symlink_to(target)
        fields = {"drm-driver": driver, "drm-pdev": pci, "drm-client-id": cid,
                  "drm-engine-render": f"{render} ns", "drm-engine-compute": f"{compute} ns",
                  "drm-engine-video": f"{video} ns", "drm-total-system0": memory,
                  "drm-resident-system0": "512 KiB", "drm-shared-system0": "256 KiB",
                  "drm-engine-copy": "9000000000 ns", "drm-engine-video-enhance": "9000000000 ns"}
        if capacity is not None:
            fields["drm-engine-capacity-video"] = capacity
        self.write(path / "fdinfo" / str(fd), "\n".join(f"{k}:\t{v}" for k, v in fields.items() if k not in omit))

    def start(self, **kwargs):
        self.device()
        self.client(**kwargs)

    def rename_card(self):
        old = self.dev / "drm" / self.card
        self.card = "card19"
        old.rename(self.dev / "drm" / self.card)


def matches(sample, expected):
    for key, want in expected.items():
        got = sample[key]
        if isinstance(want, float):
            if got is None or not math.isclose(got, want, rel_tol=1e-8, abs_tol=1e-8):
                return False
        elif got != want:
            return False
    return True


def scenario(binary, tree, name, steps):
    print(f"[{name}]", flush=True)
    tree.reset()
    s = Sampler(binary)
    try:
        for ms, change, expected, label in steps:
            if change:
                change(tree)
            sample = s.sample(ms)
            check(label, matches(sample, expected), json.dumps(sample))
    finally:
        rc, err = s.close()
    check("clean exit (ASan/UBSan)", rc == 0 and not err.strip(), f"rc={rc} {err[:500]}")


def fake_tests(binary, t):
    scenario(binary, t, "deltas, allocated memory, requested clock, cache, overlap and two video engines", [
        (100, lambda t: t.start(memory="1 MiB"), {"status": "active", "usage": None, "video": None,
          "memory": 1048576, "clock": 550, "clockMax": 2000, "clients": 1}, "baseline; allocated, not resident; requested, not actual"),
        (1100, lambda t: t.client(render=400000000, compute=200000000, video=300000000, memory="1 MiB"),
         {"usage": 60.0, "render": 40.0, "compute": 20.0, "video": 30.0}, "independent 40 + 20% graphics and 30% E/D"),
        (1100, lambda t: (t.client(render=900000000, compute=600000000, video=900000000, memory="2 MiB"),
                         t.write(t.gt / "rps_cur_freq_mhz", 1200), t.write(t.gt / "rps_max_freq_mhz", 1400)),
         {"usage": 60.0, "memory": 1048576, "clock": 550, "clockMax": 2000}, "same tick caches all values"),
        (900, None, {"usage": 60.0, "memory": 1048576, "clock": 550}, "older tick cached"),
        (2100, None, {"usage": 90.0, "video": 60.0, "memory": 2097152, "clock": 1200, "clockMax": 1400}, "newer tick refreshes values and mutable maximum"),
        (3100, lambda t: t.client(render=1700000000, compute=1400000000, video=2400000000),
         {"usage": 100.0, "render": 80.0, "compute": 80.0, "videoRaw": 150.0, "video": 100.0, "videoCapacity": 2}, "valid overlap and dual-video work saturate only displayed index"),
    ])

    def mixed(t, step=0):
        if not step:
            t.device()
        for pid, fd in ((100, 3), (100, 4), (200, 3)):
            t.client(pid=pid, fd=fd, render=300000000 * step, compute=100000000 * step, video=200000000 * step, memory="1 KiB")
        t.client(pid=300, cid=4294967297, render=100000000 * step, compute=100000000 * step, video=100000000 * step, memory="2 KiB")
        t.client(pid=400, driver="amdgpu", pci="0000:04:00.0", render=999999999, memory="999 MiB")
        t.client(pid=500, pci="0000:00:03.0", render=999999999, memory="999 MiB")
        t.client(pid=600, target="/dev/zero", memory="999 MiB")

    scenario(binary, t, "PCI/driver/device filtering and global descriptor/fork deduplication", [
        (100, mixed, {"clients": 2, "memory": 3072, "usage": None}, "two unique clients, including a 64-bit ID"),
        (1100, lambda t: mixed(t, 1), {"clients": 2, "memory": 3072, "usage": 60.0, "video": 30.0}, "duplicates and other devices do not inflate any reading"),
    ])

    scenario(binary, t, "driver timing overshoot remains a visible work index", [
        (100, lambda t: t.start(), {"usage": None}, "baseline"),
        (1100, lambda t: t.client(render=1100000000), {"render": 110.0, "usage": 100.0}, "bounded driver overshoot does not cause gaps"),
        (2100, lambda t: t.client(render=1200000000), {"render": 10.0, "usage": 10.0}, "next interval remains correct"),
    ])

    scenario(binary, t, "video capacity changes, invalid capacity, and recovery", [
        (100, lambda t: t.start(capacity=None), {"videoCapacity": 1, "video": None}, "missing capacity defaults to one"),
        (1100, lambda t: t.client(video=500000000, capacity=None), {"video": 50.0}, "single-engine baseline"),
        (2100, lambda t: t.client(video=1500000000, capacity=2), {"video": None, "videoCapacity": 2}, "capacity change rebaselines"),
        (3100, lambda t: t.client(video=3000000000, capacity=2), {"video": 100.0, "videoRaw": 150.0}, "more than one engine-equivalent is valid"),
        (4100, lambda t: t.client(video=3100000000, capacity=0), {"video": None, "videoCapacity": 0}, "zero capacity unavailable"),
        (5100, lambda t: t.client(video=3200000000, capacity=2), {"video": None}, "capacity restored: fresh baseline"),
        (6100, lambda t: t.client(video=3300000000, capacity=2), {"video": 10.0}, "capacity recovery"),
    ])

    def unbind(t):
        (t.sys / "bus/pci/drivers/i915" / PCI).unlink()

    scenario(binary, t, "late discovery, unbind/rebind, and DRM card renumbering", [
        (100, None, {"status": "not_found", "usage": None}, "device absent"),
        (1100, lambda t: t.start(), {"status": "active", "usage": None}, "device arrives"),
        (2100, lambda t: t.client(render=100000000), {"usage": 10.0}, "first usable interval"),
        (3100, unbind, {"status": "not_found", "memory": None}, "unbound"),
        (4100, lambda t: t.bind(), {"status": "active", "usage": None}, "rebind has no lifetime spike"),
        (5100, lambda t: t.client(render=200000000), {"usage": 10.0}, "rebound interval"),
        (6100, lambda t: t.rename_card(), {"status": "active", "usage": None, "clock": 550}, "renumbering rediscovered and baselined"),
        (7100, lambda t: t.client(render=300000000), {"usage": 10.0}, "renumbered interval"),
    ])

    def asleep(t):
        t.start()
        t.write(t.dev / "power/runtime_status", "suspended")
        (t.gt / "rps_cur_freq_mhz").unlink()
        os.mkfifo(t.gt / "rps_cur_freq_mhz")

    def wake(t, counter=0):
        (t.gt / "rps_cur_freq_mhz").unlink()
        t.write(t.gt / "rps_cur_freq_mhz", 550)
        t.write(t.dev / "power/runtime_status", "active")
        t.client(render=counter)

    scenario(binary, t, "sleep guard and wake baseline (clock FIFO would block if read)", [
        (100, asleep, {"status": "suspended", "clock": None, "memory": None, "procReadable": False}, "no dynamic reads while asleep"),
        (1100, wake, {"status": "active", "usage": None}, "wake baseline"),
        (2100, lambda t: t.client(render=100000000), {"usage": 10.0}, "awake interval"),
        (3100, lambda t: t.write(t.dev / "power/runtime_status", "suspending"), {"status": "suspended", "usage": None}, "suspending clears history"),
        (4100, lambda t: (t.write(t.dev / "power/runtime_status", "active"), t.client(render=1000000000)), {"usage": None}, "resume discards sleep lifetime"),
        (5100, lambda t: t.client(render=1100000000), {"usage": 10.0}, "resume interval"),
    ])

    scenario(binary, t, "backward reports, corrupt jumps, missing fields, exit and client ID reuse", [
        (100, lambda t: t.start(render=100000000), {"usage": None}, "initial lifetime not counted"),
        (1100, lambda t: t.client(render=300000000), {"usage": 20.0}, "known interval"),
        (2100, lambda t: t.client(render=200000000), {"usage": None}, "backward report retains high-water mark"),
        (3100, lambda t: t.client(render=500000000), {"usage": 10.0}, "catch-up uses full two-second elapsed time"),
        (4100, lambda t: t.client(render=1000000000000), {"usage": None}, "corrupt jump is not hidden by saturation"),
        (5100, lambda t: t.client(render=600000000), {"usage": None}, "fresh baseline after corrupt jump"),
        (6100, lambda t: t.client(render=700000000), {"usage": 10.0}, "corrupt jump recovered"),
        (7100, lambda t: t.client(omit=("drm-engine-render",)), {"usage": None}, "missing engine unavailable"),
        (8100, lambda t: t.client(render=800000000), {"usage": None}, "restored engine baseline"),
        (9100, lambda t: t.client(render=900000000), {"usage": 10.0}, "restored engine interval"),
        (10100, lambda t: shutil.rmtree(t.proc / "100"), {"clients": 0, "memory": 0, "usage": 0.0}, "no visible clients: no stale lifetime or allocation"),
        (11100, lambda t: t.client(pid=200, render=1000000000000), {"clients": 1, "usage": None}, "reused ID is a new lifetime"),
        (12100, lambda t: t.client(pid=200, render=1000100000000), {"usage": 10.0}, "reused ID interval"),
    ])

    scenario(binary, t, "allocated bytes, units, partial fields and integer overflow", [
        (100, lambda t: t.start(memory="2 MiB"), {"memory": 2097152}, "allocated bytes do not add resident/shared categories"),
        (1100, lambda t: t.client(memory="2048 B"), {"memory": 2048}, "bytes unit"),
        (2100, lambda t: t.client(memory="3 kB"), {"memory": 3072}, "legacy kB is binary here"),
        (3100, lambda t: t.client(memory="17"), {"memory": 17}, "unitless bytes"),
        (4100, lambda t: t.client(memory="-1 KiB"), {"memory": None}, "negative bytes unavailable"),
        (5100, lambda t: t.client(memory="18446744073709551615 MiB"), {"memory": None}, "unit conversion overflow rejected"),
        (6100, lambda t: t.client(memory="junk"), {"memory": None}, "malformed allocation unavailable"),
        (7100, lambda t: (t.client(memory="1 MiB"), t.client(pid=200, cid=2, memory="junk")),
         {"clients": 2, "memoryClients": 1, "memory": 1048576}, "known allocation survives another client's missing data"),
        (8100, lambda t: (t.client(memory="18446744073709551615"), t.client(pid=200, cid=2, memory="1")),
         {"memory": None}, "sum overflow rejected"),
        (9100, lambda t: (t.client(memory="0"), t.client(pid=200, cid=2, memory="0")), {"memory": 0}, "valid zero recovers"),
    ])

    scenario(binary, t, "proc and known-Intel descriptor access failures recover without false zero", [
        (100, lambda t: t.start(), {"usage": None}, "baseline"),
        (1100, lambda t: t.client(render=100000000), {"usage": 10.0}, "valid interval"),
        (2100, lambda t: os.chmod(t.proc / "100/fdinfo/3", 0), {"incomplete": True, "memory": None, "usage": None}, "unreadable known Intel fd is unavailable, not idle"),
        (3100, lambda t: (os.chmod(t.proc / "100/fdinfo/3", 0o644), t.client(render=300000000)), {"usage": None, "memory": 1048576}, "descriptor recovery baseline"),
        (4100, lambda t: t.client(render=400000000), {"usage": 10.0}, "descriptor interval restored"),
        (5100, lambda t: os.chmod(t.proc, 0), {"procDenied": True, "usage": None, "clock": 550}, "proc denied does not hide known clock"),
        (6100, lambda t: (os.chmod(t.proc, 0o755), t.client(render=600000000)), {"usage": None, "procDenied": False}, "proc restored baseline"),
        (7100, lambda t: t.client(render=700000000), {"usage": 10.0}, "proc restored interval"),
    ])

    for directory in ("fdinfo", "fd"):
        scenario(binary, t, f"known Intel {directory} directory denial retains unknown state until recovery or exit", [
            (100, lambda t: t.start(), {"usage": None, "memory": 1048576}, "known client baseline"),
            (1100, lambda t: t.client(render=100000000, video=200000000),
             {"usage": 10.0, "video": 20.0, "incomplete": False}, "known client interval"),
            (2100, lambda t: os.chmod(t.proc / "100" / directory, 0),
             {"incomplete": True, "usage": None, "video": None, "memory": None, "clock": 550},
             "known directory denial is unavailable, not idle"),
            (3100, None, {"incomplete": True, "usage": None, "video": None, "memory": None},
             "repeated denial does not forget the known Intel client"),
            (4100, lambda t: (os.chmod(t.proc / "100" / directory, 0o755),
                             t.client(render=400000000, video=800000000)),
             {"incomplete": False, "usage": None, "video": None, "memory": 1048576},
             "directory recovery takes fresh activity baselines"),
            (5100, lambda t: t.client(render=500000000, video=1000000000),
             {"usage": 10.0, "video": 20.0, "incomplete": False}, "recovered interval"),
            (6100, lambda t: shutil.rmtree(t.proc / "100"),
             {"clients": 0, "incomplete": False, "usage": 0.0, "video": 0.0, "memory": 0},
             "real process exit clears ownership and permits known zero"),
        ])

    def unrelated_denied(t):
        t.start()
        t.process(pid=300)
        (t.proc / "300/fdinfo").mkdir()
        os.chmod(t.proc / "300/fdinfo", 0)

    scenario(binary, t, "an unrelated protected process does not invalidate Intel readings", [
        (100, unrelated_denied, {"incomplete": False, "memory": 1048576}, "unrelated denied directory at baseline"),
        (1100, lambda t: t.client(render=100000000),
         {"incomplete": False, "usage": 10.0, "memory": 1048576}, "unrelated denial is only a coverage limit"),
        (2100, lambda t: t.client(render=200000000),
         {"incomplete": False, "usage": 10.0}, "unrelated repeated denial stays harmless"),
        (3100, lambda t: (os.chmod(t.proc / "300/fdinfo", 0o755), t.client(render=300000000)),
         {"incomplete": False, "usage": 10.0}, "unrelated access recovery preserves history"),
    ])

    def aliases(t, counter=0):
        if not counter:
            t.device()
        for pid in (100, 200):
            t.client(pid=pid, render=counter, video=counter * 2)

    scenario(binary, t, "a readable shared-client alias resolves another owner's access denial", [
        (100, aliases, {"clients": 1, "memory": 1048576}, "one client shared across two processes"),
        (1100, lambda t: aliases(t, 100000000), {"usage": 10.0, "video": 20.0}, "shared client baseline interval"),
        (2100, lambda t: (os.chmod(t.proc / "100/fdinfo", 0),
                         t.client(pid=200, render=200000000, video=400000000)),
         {"clients": 1, "incomplete": False, "usage": 10.0, "video": 20.0, "memory": 1048576},
         "readable alias keeps complete readings without double counting memory"),
        (3100, lambda t: t.client(pid=200, render=300000000, video=600000000),
         {"clients": 1, "incomplete": False, "usage": 10.0, "memory": 1048576}, "alias survives repeated denial"),
        (4100, lambda t: shutil.rmtree(t.proc / "200"),
         {"incomplete": True, "usage": None, "video": None, "memory": None},
         "loss of the readable alias reveals the still-known inaccessible owner"),
        (5100, lambda t: (os.chmod(t.proc / "100/fdinfo", 0o755),
                         t.client(render=500000000, video=1000000000)),
         {"incomplete": False, "usage": None, "memory": 1048576}, "remaining owner recovers with a fresh baseline"),
        (6100, lambda t: t.client(render=600000000, video=1200000000),
         {"incomplete": False, "usage": 10.0, "video": 20.0}, "remaining owner interval"),
    ])

    def reused_unrelated(t):
        t.process(starttime=2000)
        t.client(driver="amdgpu", pci="0000:04:00.0")
        os.chmod(t.proc / "100/fdinfo", 0)

    scenario(binary, t, "PID reuse does not retain a former Intel owner's unknown state", [
        (100, lambda t: t.start(), {"usage": None}, "original process generation"),
        (1100, lambda t: t.client(render=100000000), {"usage": 10.0}, "original Intel interval"),
        (2100, reused_unrelated,
         {"clients": 0, "incomplete": False, "usage": 0.0, "video": 0.0, "memory": 0},
         "changed starttime identifies a new unrelated protected process"),
        (3100, None, {"incomplete": False, "usage": 0.0, "memory": 0}, "unrelated reused PID stays harmless"),
        (4100, lambda t: os.chmod(t.proc / "100/fdinfo", 0o755),
         {"incomplete": False, "usage": 0.0}, "unrelated reused PID becomes readable"),
        (5100, lambda t: t.client(cid=2, render=1000000000000),
         {"clients": 1, "usage": None}, "new generation's first Intel client takes a baseline"),
        (6100, lambda t: t.client(cid=2, render=1000100000000),
         {"incomplete": False, "usage": 10.0}, "new generation's interval is valid"),
    ])

    def closed_known_fd(t):
        (t.proc / "100/fd/3").unlink()
        (t.proc / "100/fdinfo/3").unlink()
        t.client(fd=4, cid=2, driver="amdgpu", pci="0000:04:00.0")
        os.chmod(t.proc / "100/fd", 0)

    scenario(binary, t, "an unrelated denied FD does not retain a closed Intel FD in the same process", [
        (100, lambda t: t.start(), {"usage": None}, "known FD baseline"),
        (1100, lambda t: t.client(render=100000000), {"usage": 10.0}, "known FD interval"),
        (2100, closed_known_fd,
         {"clients": 0, "incomplete": False, "usage": 0.0, "video": 0.0, "memory": 0},
         "readable fdinfo enumeration proves the known FD has closed"),
        (3100, None, {"incomplete": False, "usage": 0.0, "memory": 0}, "unrelated FD denial stays harmless"),
        (4100, lambda t: os.chmod(t.proc / "100/fd", 0o755),
         {"incomplete": False, "usage": 0.0}, "unrelated FD access recovers without stale history"),
        (5100, lambda t: t.client(render=1000000000000),
         {"clients": 1, "usage": None}, "reopened Intel FD starts a new lifetime"),
        (6100, lambda t: t.client(render=1000100000000), {"usage": 10.0}, "reopened Intel FD interval"),
    ])

    scenario(binary, t, "whole-proc denial does not erase ownership needed after root recovery", [
        (100, lambda t: t.start(), {"usage": None}, "known process baseline"),
        (1100, lambda t: t.client(render=100000000), {"usage": 10.0}, "known process interval"),
        (2100, lambda t: os.chmod(t.proc, 0),
         {"procDenied": True, "usage": None, "memory": None}, "whole proc root denied"),
        (3100, lambda t: (os.chmod(t.proc, 0o755), os.chmod(t.proc / "100/fdinfo", 0)),
         {"procDenied": False, "incomplete": True, "usage": None, "video": None, "memory": None},
         "root recovery still knows the denied Intel owner"),
        (4100, None, {"incomplete": True, "usage": None, "memory": None}, "child denial remains unknown on later ticks"),
        (5100, lambda t: (os.chmod(t.proc / "100/fdinfo", 0o755), t.client(render=500000000)),
         {"incomplete": False, "usage": None, "memory": 1048576}, "child recovery takes a new baseline"),
        (6100, lambda t: t.client(render=600000000), {"usage": 10.0}, "child recovery interval"),
    ])

    scenario(binary, t, "an unreadable process identity does not erase a known denied Intel owner", [
        (100, lambda t: t.start(), {"usage": None}, "known identity baseline"),
        (1100, lambda t: t.client(render=100000000), {"usage": 10.0}, "known identity interval"),
        (2100, lambda t: (os.chmod(t.proc / "100/fdinfo", 0), (t.proc / "100/stat").unlink()),
         {"incomplete": True, "usage": None, "memory": None}, "missing stat does not prove process replacement"),
        (3100, lambda t: t.write(t.proc / "100/stat", "malformed stat"),
         {"incomplete": True, "usage": None, "memory": None}, "malformed stat preserves the known unknown owner"),
        (4100, lambda t: t.process(),
         {"incomplete": True, "usage": None, "memory": None}, "same restored starttime still belongs to the denied owner"),
        (5100, lambda t: (os.chmod(t.proc / "100/fdinfo", 0o755), t.client(render=500000000)),
         {"incomplete": False, "usage": None, "memory": 1048576}, "identity and access recovery rebaseline"),
        (6100, lambda t: t.client(render=600000000), {"usage": 10.0}, "identity recovery interval"),
    ])

    def no_clocks(t):
        t.start()
        (t.gt / "rps_cur_freq_mhz").unlink()
        (t.gt / "rps_max_freq_mhz").unlink()

    scenario(binary, t, "late/zero/malformed requested clocks and unknown runtime state", [
        (100, no_clocks, {"clock": None, "clockMax": None}, "clock files missing"),
        (1100, lambda t: (t.write(t.gt / "rps_cur_freq_mhz", 0), t.write(t.gt / "rps_max_freq_mhz", 2000)), {"clock": 0, "clockMax": 2000}, "late zero is valid"),
        (2100, lambda t: t.write(t.gt / "rps_cur_freq_mhz", "550junk"), {"clock": None}, "malformed requested clock is not actual-clock fallback"),
        (3100, lambda t: t.write(t.gt / "rps_cur_freq_mhz", 1200), {"clock": 1200}, "requested clock recovered"),
        (4100, lambda t: (t.dev / "power/runtime_status").unlink(), {"status": "unavailable", "clock": None, "usage": None}, "unknown runtime state skips dynamic reads"),
        (5100, lambda t: t.write(t.dev / "power/runtime_status", "active"), {"status": "active", "clock": 1200, "usage": None}, "runtime state restored with fresh history"),
    ])


def negative_controls(work, tree):
    original = (SRC / "linux/IntelGPU.c").read_text()
    mutations = {
        "PCI filter": ('!String_eq(driver, "i915") || !String_eq(pci, device.pci)', '!String_eq(driver, "i915")'),
        "fork deduplication": ('IntelGPU_observe(&observation);',
                               'IntelGPU_observe(&(IntelGPUObservation) { .id = observation.id ^ (strtoull(process->d_name, NULL, 10) << 32), .mask = observation.mask, .memory = observation.memory, .memoryValid = observation.memoryValid, .capacityValid = observation.capacityValid, .capacityExplicit = observation.capacityExplicit, .capacity = {observation.capacity[0], observation.capacity[1], observation.capacity[2]}, .value = {observation.value[0], observation.value[1], observation.value[2]} });'),
        "dual-video capacity": ('elapsed * current->capacity[e] * INTELGPU_ACCOUNTING_SLACK', 'elapsed * INTELGPU_ACCOUNTING_SLACK'),
    }
    for name, (old, new) in mutations.items():
        assert original.count(old) == 1, name
        source = work / "mutant.c"
        source.write_text(original.replace(old, new))
        binary = work / "mutant"
        build(binary, tree.sys, tree.proc, source)
        saved = list(failures)
        failures.clear()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            fake_tests(binary, tree)
        caught = bool(failures)
        (work / (name.replace(" ", "-") + ".log")).write_text(output.getvalue())
        failures[:] = saved
        check(f"negative control catches broken {name}", caught)


def live_tests(binary, work):
    print("[live Intel i915: readable clients, clocks, encode, decode and graphics]", flush=True)
    s = Sampler(binary)
    ms = lambda: time.monotonic_ns() // 1000000
    first = s.sample(ms())
    check("supported Intel iGPU found", first["pci"] == PCI, json.dumps(first))
    node = f"/dev/dri/by-path/pci-{PCI}-render"
    encoded = work / "intel-test.mp4"
    encode = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-vaapi_device", node,
              "-re", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=60", "-t", "5",
              "-vf", "format=nv12,hwupload", "-c:v", "h264_vaapi", "-f", "mp4", str(encoded)]
    decode = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-vaapi_device", node,
              "-hwaccel", "vaapi", "-hwaccel_output_format", "vaapi", "-re",
              "-i", str(encoded), "-t", "5", "-f", "null", "-"]
    graphics = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-init_hw_device", "vulkan=igpu:Intel",
                "-filter_hw_device", "igpu", "-re", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=60",
                "-t", "5", "-vf", "format=rgba,hwupload,avgblur_vulkan=sizeX=8:sizeY=8", "-f", "null", "-"]
    env = dict(os.environ)
    drivers = [p for p in Path("/usr/share/vulkan/icd.d").glob("*intel*.json") if "libvulkan_intel.so" in p.read_text()]
    if drivers:
        env["VK_DRIVER_FILES"] = str(sorted(drivers)[0])
    check("Intel Vulkan reference driver available", bool(drivers))
    for name, command in (("encode", encode), ("decode", decode), ("graphics", graphics)):
        p = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, env=env)
        snapshots = []
        try:
            while p.poll() is None:
                time.sleep(.35)
                snapshots.append(s.sample(ms()))
            err = p.communicate(timeout=10)[1]
        finally:
            if p.poll() is None:
                p.kill()
                p.communicate()
        check(f"Intel {name} workload succeeds", p.returncode == 0 and not err.strip(), err[:600])
        key = "usage" if name == "graphics" else "video"
        usable = [x for x in snapshots if x[key] is not None]
        peak = max((x[key] for x in usable), default=0)
        check(f"{key} responds to {name} (peak {peak:.1f}%)", peak > 0, json.dumps(snapshots[-2:]))
        check(f"{name} has valid allocated memory", any(x["memory"] is not None and x["memory"] > 0 for x in snapshots))
        check(f"{name} requested clock/max available", any(x["clock"] is not None and x["clockMax"] is not None and x["clockMax"] > 0 for x in snapshots))
    rc, err = s.close()
    check("live clean exit (ASan/UBSan)", rc == 0 and not err.strip(), err[:600])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fake-only", action="store_true")
    parser.add_argument("--mutations", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="htop-intel-tests-") as tmp:
        work = Path(tmp)
        tree = Tree(work / "root")
        fake = work / "intel-fake"
        build(fake, tree.sys, tree.proc)
        fake_tests(fake, tree)
        if args.mutations:
            negative_controls(work, tree)
        if not args.fake_only:
            live = work / "intel-live"
            build(live, "/sys", "/proc")
            live_tests(live, work)
    print("\nALL PASSED" if not failures else f"\n{len(failures)} FAILED: " + ", ".join(failures), flush=True)
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
