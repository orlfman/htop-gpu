#!/usr/bin/env python3
# Run a command, sample its amdgpu fdinfo engine counters + gpu_metrics media fields while it runs.
import glob, os, re, subprocess, sys, time

sys.dont_write_bytecode = True  # keep tools/ free of __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gpu_metrics

PDEV = "0000:04:00.0"


def fdinfo_engines(pid):
    totals = {}
    for f in glob.glob(f"/proc/{pid}/fdinfo/*"):
        try:
            txt = open(f).read()
        except OSError:
            continue
        if f"drm-pdev:\t{PDEV}" not in txt:
            continue
        for k, v in re.findall(r"^drm-engine-(?!capacity)([\w-]+):\s+(\d+)", txt, re.M):
            totals[k] = max(totals.get(k, 0), int(v))
    return totals


proc = subprocess.Popen(sys.argv[1:], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
t0 = time.monotonic()
peak, last = {}, {}
while proc.poll() is None:
    m = gpu_metrics.read()
    for k in ("average_mm_activity", "average_gfx_activity", "current_vclk0", "current_dclk0",
              "average_vclk0_frequency", "average_dclk0_frequency", "current_gfxclk"):
        if m[k] != 0xFFFF:
            peak[k] = max(peak.get(k, 0), m[k])
    last = fdinfo_engines(proc.pid) or last
    time.sleep(0.2)
print(f"exit {proc.returncode} after {time.monotonic() - t0:.1f}s")
print("fdinfo engine ns (ffmpeg, 9070 XT):", {k: v for k, v in last.items() if v})
print("gpu_metrics peaks:", peak)
