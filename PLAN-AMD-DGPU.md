# htop-gpu: AMD meters on RDNA 2 and newer dedicated cards (plan)

Status (2026-10-29): investigated, nothing implemented. Written by Claude Code.
Goal: the AMD meters work on every RDNA 2, RDNA 3 and RDNA 4 dedicated card
(RX 6000, RX 7000, RX 9000 and their Radeon Pro versions), not only the
RX 9070 XT, still without opening DRM device nodes or waking a sleeping GPU.

This is the first, narrower part of [PLAN-AMD-AGNOSTIC.md](PLAN-AMD-AGNOSTIC.md).
APUs, older cards and the other `gpu_metrics` layouts stay in that plan for later.

Sources: Linux v7.3 `amdgpu_discovery.c` (GC versions, APU flag),
`amdgpu_pm.c` (which sysfs/hwmon files exist), the SMU drivers
`sienna_cichlid_ppt.c` (RDNA 2), `smu_v13_0_0_ppt.c` / `smu_v13_0_7_ppt.c`
(RDNA 3), `smu_v14_0_2_ppt.c` (RDNA 4), and this card's sysfs.

## Why this scope is small

Every one of these cards already reports what the meters read, in the same form
as the RX 9070 XT:

- `gpu_metrics` is **v1.3** (120 bytes) on all of them: all four SMU drivers call
  `smu_cmn_init_soft_gpu_metrics(gpu_metrics, 1, 3)`. So `current_vclk0` /
  `current_dclk0` at 60/62 and `average_mm_activity` at 20 work unchanged. No
  new layouts are needed.
- hwmon: `temp1-3` (edge, junction, mem) on all SOC15 dGPUs, `freq1` (sclk) and
  `freq2` (mclk) on all dGPUs, `fan1_input` / `fan1_max` where the driver can
  read fan RPM (all of these), `power1_cap`. Power is `power1_average` or
  `power1_input`, whichever the SMU supports; the code already tries both.
- sysfs: `gpu_busy_percent`, `mem_busy_percent` (APUs only lack it),
  `mem_info_vram_used/_total`, `pp_dpm_mclk`, `pp_dpm_sclk`.
- Memory: every RDNA 2/3/4 dGPU uses GDDR6, and on all of them amdgpu reports
  the memory clock so that data rate = mclk x 16 (16 Gbps RX 6800 XT tops out at
  1000 MHz, 20 Gbps RX 7900 XTX at 1250 MHz, this card at 1258 MHz).

## The one real gap: video engine load on RDNA 2

`vcn_busy_percent` is only created for graphics IP 11.0.0-4 and 12.0.0/1 among
dGPUs (plus some APUs). RDNA 2 dGPUs (GC 10.3.0/2/4/5) don't have it. The same
number is in `gpu_metrics` as `average_mm_activity`, which `sienna_cichlid_ppt.c`
fills from the firmware's VCN activity. So: read `vcn_busy_percent` when it
exists, otherwise `average_mm_activity` from the sample's `gpu_metrics` read
(already read every tick for the clocks, so no extra file read).

On RDNA 3 with two VCN instances (RX 7900), `gpu_metrics` gives the max of the
two, and `vcn_busy_percent` does the same. RX 6500 XT / 6400 (Navi 24) can only
decode; the meter caption is `VCN`, so nothing needs to change.

## Telling which cards qualify, without device IDs

amdgpu exposes the IP discovery table in sysfs on every card that has one (all
RDNA cards do):

```
/sys/bus/pci/devices/<pci>/ip_discovery/die/0/GC/0/major, minor, revision
```

Here: `GC 12.0.1`. The kernel's APU flag isn't in sysfs, but `amdgpu_discovery.c`
sets it from the GC version alone, so a list of the dedicated-card GC versions
is exact:

| GC | Chip | Cards |
| --- | --- | --- |
| 10.3.0 | Navi 21 | RX 6800 / 6800 XT / 6900 XT / 6950 XT |
| 10.3.2 | Navi 22 | RX 6700 / 6700 XT / 6750 XT |
| 10.3.4 | Navi 23 | RX 6600 / 6600 XT / 6650 XT |
| 10.3.5 | Navi 24 | RX 6500 XT / 6400 |
| 11.0.0 | Navi 31 | RX 7900 GRE / XT / XTX |
| 11.0.2 | Navi 33 | RX 7600 / 7600 XT |
| 11.0.3 | Navi 32 | RX 7700 XT / 7800 XT |
| 12.0.0 | Navi 44 | RX 9060 XT |
| 12.0.1 | Navi 48 | RX 9070 / 9070 XT / 9070 GRE |

The APU GC versions (10.3.1/3/6/7, 11.0.1/4, 11.5.x, 11.7.x) are left out on
purpose, which also means the Radeon iGPU on a Ryzen + Radeon desktop is skipped
automatically. A GC version not in the table (a future card, or `ip_discovery`
missing) keeps today's behavior: no card, the meters say N/A. Adding a future
generation is one line once its `gpu_metrics` version and memory type are known.

As a second check, the first `gpu_metrics` read must say format 1 / content 3
(as now). A card that passes the GC check but reports anything else shows N/A
for the video clocks only, as today.

## Changes to the code

All in `linux/AMDGPU.c`; the meter file and upstream files are untouched.

1. **Card table keyed on GC version** instead of PCI device ID:
   `{ gcMajor, gcMinor, gcRevision, memRateMultiplier }`. The `name` field goes
   (it's never shown). Discovery picks the first amdgpu device by PCI address
   whose GC version is in the table, so a machine with one of these cards plus
   an AMD iGPU picks the card.
2. **VCN fallback** to `average_mm_activity` when `vcn_busy_percent` is absent,
   decided once at discovery (absent = ENOENT), not retried every tick.
3. **Clock bar scale**: today it's seeded at 3000 MHz for this card because the
   top `pp_dpm_sclk` level (2400 MHz here) is below real boost (about 3000 MHz).
   Generic: seed from the top `pp_dpm_sclk` level, then grow to the highest clock
   seen, as now. To keep this card's output byte for byte, the table keeps an
   optional per-GC seed: GC 12.0.1 → 3000. Others start at their `pp_dpm_sclk`
   top and settle after the first boost.
4. **Absent vs failed** one-time values, the part of the agnostic plan's step 2
   that these cards need: a missing `fan1_max` (a passively cooled Radeon Pro, or
   a board without fan control) must not make `AMDGPU_staticComplete()` retry
   forever. Absent (ENOENT, label not found) = not on this card, stays N/A;
   present but unreadable = retried, as now.

What stays out: multiple dedicated cards (the first by PCI address is used, as
now; `Name(n)` selection is in the agnostic plan), APUs, RDNA 1 and older.

## Tests

- Extend `tools/fake-sysfs.py` with `--gc MAJOR.MINOR.REV` (writes the
  `ip_discovery` tree) and `--no-vcn-busy`. The default stays this card.
- In `tools/test-sampler.py`, under one running sampler: an RDNA 2 tree
  (GC 10.3.0, no `vcn_busy_percent`, video from `gpu_metrics`), an RDNA 3 tree
  (GC 11.0.0), an APU GC (10.3.6) that must be skipped, an unknown GC that must
  show N/A, an iGPU at a lower PCI address than the card (card must win), and a
  tree without `fan1_max` (no endless retry). The existing recovery cases keep
  passing; this card's fake tree must produce exactly the same output.
- `tools/check-style.sh`, ASan/UBSan run, and a live check on this card that
  the header matches the current build byte for byte.

## Order of work

1. GC-version card table and discovery, with fake-tree tests. On this card
   nothing changes.
2. VCN fallback from `gpu_metrics` for RDNA 2.
3. Absent vs failed one-time values.
4. Clock seed from `pp_dpm_sclk` for cards without a table seed.
5. README and repo descriptions: "RX 6000, 7000 and 9000 cards (tested on an
   RX 9070 XT)". Patches re-exported, package bumped.

Each step is its own commit in `src/htop` and keeps the existing suites passing
unchanged.

## Limits

Only an RX 9070 XT is here. RDNA 2 and 3 are covered by fake trees built from the
kernel source, which proves the parsing and the selection logic but not real
firmware values (for example how RDNA 2 firmware fills `average_mm_activity`
during a pure decode). The README should say so and ask for reports.
