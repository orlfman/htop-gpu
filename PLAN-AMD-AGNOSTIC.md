# htop-gpu: AMD meters for any AMD GPU (plan)

Status (2026-10-29): investigation done, nothing implemented. Written by Claude Code.
First part, RDNA 2 and newer dedicated cards: [PLAN-AMD-DGPU.md](PLAN-AMD-DGPU.md).
Goal: the AMD meters work on any GPU driven by `amdgpu`, not only the RX 9070 XT,
without opening DRM device nodes and without waking a sleeping GPU.

Sources: Linux v7.3 (`drivers/gpu/drm/amd/include/kgd_pp_interface.h`,
`drivers/gpu/drm/amd/pm/amdgpu_pm.c` and its hwmon kernel-doc,
`include/uapi/drm/amdgpu_drm.h`) and the current `linux/AMDGPU.c`.

## What is already generic

These come from amdgpu's standard sysfs/hwmon files and need no change:
`gpu_busy_percent`, `mem_busy_percent`, `mem_info_vram_used/_total`,
`power1_average` / `power1_input` / `power1_cap`, `freq1/2_input` found by label,
`temp1-3` found by label, `fan1_input/_max`, `power/runtime_status`, discovery by
PCI address through `/sys/bus/pci/drivers/amdgpu`, and the retry/recovery logic
from the audit fixes.

## What is tied to the RX 9070 XT, and the generic version

| Today | Generic |
| --- | --- |
| Card table with only `0x7550` | Accept every device bound to amdgpu; the table becomes optional extras (see VRAM speed) |
| `gpu_metrics` v1.3 only (120 bytes, rev 1.3) | Accept the versions below, checked by size **and** format/content revision |
| `vcn_busy_percent` only | Fall back to `gpu_metrics` activity when the file is missing |
| Clock bar seeded at 3000 MHz | Seed from the top `pp_dpm_sclk` level, then grow to the highest clock seen (as now) |
| Data rate = mclk x 16 (GDDR6) | Only for cards whose memory type is known; otherwise show MHz only |

## gpu_metrics layouts

Offsets computed by compiling the kernel's own struct definitions (offsetof),
not read by hand. All fields are `uint16_t`, `0xFFFF` means unset.

| Version | Size | Used by | current vclk / dclk | Video activity |
| --- | --- | --- | --- | --- |
| 1.0 | 80 | older dGPUs (Navi 1x era) | 60 / 62 | `average_mm_activity` @ 32 |
| 1.1 | 96 | dGPUs | 60 / 62 | @ 20 |
| 1.2 | 104 | dGPUs | 60 / 62 | @ 20 |
| 1.3 | 120 | dGPUs incl. RDNA 3/4 (this card) | 60 / 62 | @ 20 |
| 2.0 | 120 | APUs | 88 / 90 | `average_mm_activity` @ 42 |
| 2.1–2.4 | 120 / 120 / 128 / 152 / 168 | APUs | 84 / 86 | @ 30 |
| 3.0 | 264 | newer APUs | no current clock; `average_vclk_frequency` @ 184 | `average_vcn_activity` @ 44 |
| 1.4–1.9 | 288+ / attribute list | Instinct datacenter | arrays per instance | out of scope |

v1.3 and v2.0 are both 120 bytes, so the format revision (1 vs 2) must be checked,
not just the size. Anything not in this table keeps showing `N/A` for the video
clocks, as today.

## vcn_busy_percent

`amdgpu_pm.c` only creates it for graphics IP 9.3.0, 10.3.1/3/6/7, 11.0.0-4,
11.5.0-3 and 12.0.0/1 (roughly RX 6000-era APUs and RDNA 3/4). Everything else
uses the `gpu_metrics` video activity above, which every listed version has.

## Sensors that a card may simply not have

Per the hwmon kernel-doc: `temp2` (junction) and `temp3` (memory) and their limits
exist on SOC15 dGPUs only (Vega and newer). APUs have no memory clock (`freq2`),
and on APUs `mem_busy_percent` is unsupported. Fans exist only where the board
has one.

Today `AMDGPU_staticComplete()` (audit finding 4) waits until **every** one-time
value reads, so on such a card it would retry forever. The fix: decide per value
at discovery whether the card has it.

- File or label **absent** (ENOENT, label not found): not on this card. The value
  stays N/A and is not retried. Re-checked only on rediscovery (card rebound,
  hwmon renumbered).
- File **present but unreadable or garbage**: retried, as now.

Tests: fake trees modeled on an APU (edge temp only, no fan, no `freq2`), an older
dGPU without `vcn_busy_percent` (video from `gpu_metrics`), and each `gpu_metrics`
version above, plus the existing recovery cases, all under one running sampler.

## VRAM speed

The memory type (GDDR6, HBM, DDR5...) is only exposed through the
`AMDGPU_INFO_DEV_INFO` ioctl, which needs an open DRM node; opening one runtime
resumes the GPU. So the generic meter shows `VRAM clock: 1258MHz busy:12%`, and
the data rate only for cards in a small table with a known multiplier (keep
`0x7550` → GDDR6 x16). The table holds nothing else.

## Which card

`Header_addMeterByName()` already parses `Name(n)` for every meter, the same way
`CPU(3)` works, so each meter gets a `param`.

- `param` 0 (the default, and what F2 Setup adds): the "main" card, chosen as the
  one with the largest `mem_info_vram_total` (the discrete card on an APU + dGPU
  laptop), ties broken by lowest PCI address.
- `param` n > 0: the n-th amdgpu device by PCI address, for people who edit their
  htoprc. F2 Setup would only offer the default unless `AvailableMetersPanel.c`
  is changed, which is upstream code; leave that out at first.
- The sampler keeps one sample per card, still read at most once per tick.

## APU caveats

- "VRAM" on an APU is a small carve-out of system RAM; most GPU memory is in GTT.
  Show `mem_info_gtt_used/_total` on cards whose VRAM is small (say under 2 GiB),
  or add GTT as a second item in the VRAM meter.
- `power1_*` on an APU includes the CPU (kernel-doc). Say so in the meter
  description; the caption stays.
- Temperature colors: with only `temp1`, the bar follows edge instead of junction.

## Order of work

1. `gpu_metrics` versions 1.0-1.3 and 2.0-2.4 / 3.0, with fake-table tests per
   version. Smallest change, no behavior change on this card.
2. Absent vs failed sensors in the one-time reads, with APU-like and older-dGPU
   fake trees.
3. Drop the device-ID requirement; table only for known memory multipliers.
4. Card selection (largest VRAM default, `Name(n)` param), per-card samples.
5. APU memory (GTT) and the power description.
6. README and descriptions: from "RX 9070 XT" to "AMD GPUs (tested on RX 9070 XT)".

Every step keeps the current RX 9070 XT output byte for byte; the existing suites
must keep passing unchanged.

## Limits

Only an RX 9070 XT is available here. Other generations are covered by fake trees
built from the kernel's documented layouts, which proves the parsing but not real
firmware behavior. Real reports from other cards would be the only way to be sure.
