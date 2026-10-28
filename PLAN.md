# htop-gpu: plan

Status (2026-10-28): steps 1–2 done, committed and pushed on `amdgpu-meters`
(`0c74a6b7` sampler, `4875c09e` GPU usage / VRAM / power meters). Nothing
installed. Next: step 3 (temps and both clock meters).

In progress: nobody.

GitHub (both private): https://github.com/orlfman/htop-gpu (this folder) and
https://github.com/orlfman/htop (branch `amdgpu-meters`).

Agents: read `AGENTS.md` first (shared rules, turn-taking, checks).
History: `CHANGELOG.md`.

Goal: a patched htop 3.5.3 (same version CachyOS ships) with header meters for the
RX 9070 XT. Stock htop stays intact otherwise: the existing GPU meter and the
`GPU%` / `GPU_TIME` process columns keep working as they do now.

Scope: a personal build, not meant for upstream htop. It may go on my own GitHub
later as a personal fork. htop is GPLv2+, so a published copy keeps that license
and the source; the new files already carry GPLv2+ headers.

## Staying close to upstream

It's a custom build, not a split from htop, so it follows upstream's rules to keep
new htop releases easy to pick up:

- **Code style:** `docs/styleguide.md` and the repo's `AGENTS.md` / `CLAUDE.md`.
  3-space indent, `Module_function()` names, `static` unless public API, no
  function-like macros, `String_*` helpers from `XUtils.h`, plain C99. Every file
  includes headers for everything it uses directly, in upstream's include order.
- **Style check:** `tools/check-style.sh` must print `STYLE OK`. It runs
  include-what-you-use with upstream's `iwyu/htop.imp` mapping and upstream's
  astyle baseline (`astyle -n -xb -s3 -p -xg -c -k1 -W1 -H`, shown as a diff,
  files untouched). It only checks the files htop-gpu adds on top of the upstream
  tag: upstream's own files aren't fully IWYU / astyle clean in 3.5.3 (e.g.
  `linux/GPU.c`), and fixing them would only make rebasing harder.
- **Minimal diff to upstream files:** new code lives in new files
  (`linux/AMDGPU*`). Existing files only get registration lines (`Makefile.am`,
  `linux/Platform.c`). Upstream code isn't reformatted or cleaned up, and colors,
  helpers and meter modes are reused rather than extended.
- **Commits:** a small set of self-contained commits on `amdgpu-meters`, each one
  building and working, with descriptive messages. No merge commits; fixes get
  squashed into the commit they fix. AI use is disclosed with a `Co-Authored-By:`
  trailer naming the agent and model, so each agent's commits are told apart
  (upstream's `AGENTS.md` accepts that or `Assisted-by:`).
  **No `Signed-off-by:`**, since nothing goes upstream.
- **New htop release:** `git fetch upstream --tags`, then
  `git rebase --onto <new tag> <old tag> amdgpu-meters`, rebuild, run
  `tools/test-sampler.py` and `tools/check-style.sh`, then bump the PKGBUILD.

Card: Navi 48, PCI ID `1002:7550`, XFX board (`1eae:8811`), slot `0000:04:00.0`,
Samsung GDDR6. Kernel 7.3.0-4-cachyos.

## Meters

| # | Meter | htoprc name | Caption | Source | Text mode | Bar / graph |
|---|-------|-------------|---------|--------|-----------|-------------|
| 1 | GPU usage | `AMDGPUUsage` | `GPU` | `gpu_busy_percent` | `GPU:45%` | 0–100%, bar text `45%` |
| 2 | VRAM | `AMDGPUVRAM` | `VRM` | `mem_info_vram_used` / `mem_info_vram_total` | `VRM:15.9G used:3.21G` | used / total, bar text `3.21G/15.9G` |
| 3 | Power | `AMDGPUPower` | `Pwr` | hwmon `power1_average` / `power1_cap` | `Pwr:245W cap:304W` | 0 to power cap, bar text `245W/304W` |
| 4 | Temps | `AMDGPUTemp` | `GTmp` | hwmon `temp1/2/3_input` + `_crit` | `edge 52°C junction 68°C mem 70°C` | junction vs its crit |
| 5 | GPU clock | `AMDGPUClock` | `Clk` | hwmon `freq1_input` (sclk) | `2950MHz` | vs highest clock seen |
| 6 | VRAM clock | `AMDGPUMemClock` | `MClk` | hwmon `freq2_input` (mclk) + `mem_busy_percent` | `1258MHz 20.1Gbps ctrl 12%` | vs 1258 MHz |
| 7 | Video engine | `AMDGPUVideo` | `VCN` | `vcn_busy_percent` + `gpu_metrics` vclk/dclk | `100% vclk 2933 dclk 2200MHz` | 0–100% |

Each one is a separate meter, so it can be placed, moved and switched between
bar / text / graph / LED in F2 Setup like any built-in meter. Captions and names
are placeholders until we settle them. Rows 1–3 are built (step 2) and show the
real output.

Caption rule (upstream): bar and graph modes draw only the first 3 characters of
a caption, so bar-mode meters use 3-character captions (`Mem`, `Swp`, `GPU`),
and text mode is `caption` + `:` + values from the meter's display function.
That's why VRAM is `VRM`, not `VRAM` (which a bar would cut to `VRA`). When a
value is missing the meter shows `N/A`, and `sleep` when the card is runtime
suspended.

All sysfs paths are under `/sys/bus/pci/devices/0000:04:00.0/`; hwmon is the
`hwmon/hwmonN/` dir inside it (named `amdgpu`).

## What the card actually reports (measured 2026-10-28)

Idle readings, desktop only:

| File | Value | Meaning |
|------|-------|---------|
| `gpu_busy_percent` | 5 | % |
| `mem_busy_percent` | 1 | memory controller % |
| `vcn_busy_percent` | 0 | video engine % |
| `mem_info_vram_used` / `_total` | 0.89 GB / 17.1 GB (15.9 GiB) | bytes |
| `power1_average` / `power1_cap` | 32 W / 304 W (cap range 212–340) | µW, label `PPT` |
| `temp1/2/3_input` | edge 37, junction 39, mem 38 °C | m°C, crit 110 / 110 / 108 |
| `freq1_input` (sclk) | 1559 MHz | Hz |
| `freq2_input` (mclk) | 456 MHz | Hz, top DPM level 1258 |
| `gpu_metrics` | 120 bytes, revision 1.3 | binary, `struct gpu_metrics_v1_3` |

Things that shape the design:

- **GPU clock has no usable max.** `pp_dpm_sclk` tops out at 2400 MHz even though
  the card boosts to around 3 GHz, and there's no `pp_od_clk_voltage` (overdrive
  bit is off in `ppfeaturemask`; leave it off). So the clock bar is seeded at
  3000 MHz and grows to the highest clock seen.
- **VRAM speed.** mclk 1258 MHz × 16 = 20.1 Gbps per pin, which is the card's
  rated GDDR6 speed. The ×16 factor is GDDR6-specific, so it lives in the card table.
- **RDNA 4 has no `pp_dpm_vclk` / `pp_dpm_dclk`.** Video clocks exist only in
  `gpu_metrics` (`current_vclk0` at byte 60, `current_dclk0` at byte 62).
  During encode/decode they hit 2933 / 2200 MHz; idle is 25 / 25.
- **`gpu_metrics` matches hwmon** (temps, power, clocks all agree), so hwmon stays
  the main source since it's stable ABI, and `gpu_metrics` is only used for the
  two video clocks.

## Encode and decode: one meter, not two

Tested with VA-API on the 9070 XT (pinned to
`/dev/dri/by-path/pci-0000:04:00.0-render`, since renderD128 is the iGPU):

- 4K HEVC **encode**: ffmpeg's fdinfo showed `drm-engine-enc` (plus a little `compute`)
- 4K HEVC **decode**: fdinfo showed `drm-engine-enc` only, no `dec`
- `vcn_busy_percent` and `gpu_metrics.average_mm_activity` matched in every sample
  (0 → 75 → 100%) for both workloads

RDNA 4's video engine runs encode and decode through one shared queue, and the
kernel exposes a single busy % for it. There's nothing to tell the two apart, so
the plan is **one "Video engine" meter covering both**. If a later kernel splits
the counters, the meter can split too.

Possible later addition: show which processes are using the video engine (their
fdinfo `enc` time goes up), which tells you at a glance whether it's mpv
(decode) or ffmpeg / OBS (encode).

## Design

New files, so the patch stays self-contained and rebases easily:

- `linux/AMDGPU.c`, `linux/AMDGPU.h`: finds the card, reads sysfs, holds the
  card table, decodes the two `gpu_metrics` fields.
- `linux/AMDGPUMeter.c`, `linux/AMDGPUMeter.h`: the seven `MeterClass`
  definitions, modeled on `linux/ZramMeter.c`.

Existing files touched:

- `linux/Platform.c`: add the seven classes to `Platform_meterTypes[]` after
  `GPUMeter_class`.
- `Makefile.am`: add the files to the Linux header/source lists only (not the
  PCP lists, which also pull some `linux/` files).
- No `CRT.c` changes: reuse existing colors (`METER_VALUE`, `METER_VALUE_OK/WARN/ERROR`,
  `GPU_ENGINE_*`, memory colors) instead of adding new ones to all 8 color schemes.

Behavior:

- **Finding the card:** scan `/sys/bus/pci/drivers/amdgpu/` for `1002:7550` and
  store the PCI address. `cardN` and `hwmonN` numbers change between boots, so
  neither is ever hardcoded.
- **One read per refresh:** all seven meters share one cached sample, refreshed at
  most once per htop tick (keyed on `host->monotonicMs`, the same trick
  `Platform_setGPUValues` uses). That's about 15 small files per tick at your
  1.5 s delay. Nothing is read unless one of these meters is in the header.
- **Reads** go through htop's `Compat_readfile`.
- **Runtime PM guard:** check `power/runtime_status` first; if `suspended`, show
  `sleep` and touch nothing else, because reading hwmon would wake the card. Even
  the one-time values (VRAM total, mclk levels, temp limits) wait until the card
  is seen awake, since `pp_dpm_mclk` can wake it too. With `amdgpu.runpm=0` it
  never sleeps now, but the guard costs nothing.
- **Test hook:** the sysfs root is a compile-time macro (`AMDGPU_SYSFS_ROOT`,
  default `/sys`), so `tools/` can point the sampler at a fake tree. htop itself
  is always built with the default.
- **`gpu_metrics` safety:** only decoded if the header says 120 bytes, revision 1.3.
  Anything else means the vclk/dclk values show `N/A`; the video % still works.
- **Missing file:** that value shows `N/A`. Never crash, never show garbage.
- **Temps** follow htop's existing °C/°F setting. Colors relative to each sensor's
  `_crit`: normal, warn at crit − 20, red at crit − 10 (junction 90 / 100 °C,
  mem 88 / 98 °C). Easy to tune.
- **Card table:** one row for now: `0x7550` → "RX 9070 XT", GDDR6 ×16, clock bar
  seed 3000 MHz. Other amdgpu cards make the meters show `N/A` until they get a
  row. Adding a card means adding a row.

## Build and packaging

Planned folder layout:

```
htop-gpu/                    git repo (ignores src/, test/, makepkg output)
  AGENTS.md                  shared agent guide (Codex reads it directly)
  CLAUDE.md                  imports AGENTS.md for Claude Code
  CHANGELOG.md               one entry per agent session, newest first
  PLAN.md
  packaging/
    PKGBUILD                 Arch's htop PKGBUILD + our patches
    000N-*.patch             exported from src/htop with git format-patch
  src/htop/                  separate clone, branch amdgpu-meters on tag 3.5.3
  test/htoprc                throwaway config for test runs
  tools/
    amdgpu-sample.c          test driver: stdin timestamps in, JSON samples out
    build-sampler.sh         builds it with ASan/UBSan, optional fake sysfs root
    test-sampler.py          the sampler test suite (see Test plan)
    check-style.sh           IWYU + astyle on the files htop-gpu adds
    fake-sysfs.py            frozen copy of the card's sysfs, optionally broken
    build-htop-fake.sh       htop binary that reads a fake-sysfs tree
    gpu_metrics.py           gpu_metrics v1.3 decoder
    vcn_probe.py             runs a command, samples fdinfo + gpu_metrics
```

Dev loop:

- `./autogen.sh && ./configure <Arch's flags> --enable-debug && make` inside `src/htop`
- Run with `HTOPRC=<project>/test/htoprc ./htop` so the real
  `~/.config/htop/htoprc` never gets rewritten by a test build.

Package:

- `pkgname=htop-gpu`, `provides=(htop)`, `conflicts=(htop)`.
- Same signed upstream git tag as Arch, plus our patch with a checksum.
- Same configure flags as Arch: affinity, capabilities, delayacct, sensors,
  unicode. Arch also passes `--enable-openvz` and `--enable-vserver`, but 3.5.3's
  configure no longer knows them and ignores them, so ours drops them.
- Version string `3.5.3-1-gpu`, so `htop --version` shows it's the patched build.
- `makepkg` uses `~/.config/pacman/makepkg.conf` (arrowlake-s flags, `BUILDDIR=/tmp/makepkg`).
- The PKGBUILD lives in `packaging/`, not the project root: without `BUILDDIR` /
  `SRCDEST`, makepkg unpacks into `src/` and clones into `htop/` next to the
  PKGBUILD, and `src/` would collide with the dev clone.
- Install with `makepkg -si` from `packaging/`; pacman offers to replace `htop`.

Rollback: `sudo pacman -S htop` swaps the repo build back in. Stock htop skips
meter names it doesn't know and drops them from htoprc the next time it saves,
so back up `htoprc` before switching.

Updates: since the package name differs, `pacman -Syu` won't touch htop-gpu. It
also won't update it. A small `tools/check-upstream` script compares
`pacman -Si htop` against the installed version. When htop bumps: update
`pkgver`, rebase the patch, rebuild.

## Test plan

Sampler (done, `python3 -I tools/test-sampler.py`, about 30 s):

- Exact match against a frozen copy of the card's sysfs files, with expected
  values computed separately in Python.
- 17 broken-tree cases: suspended card, missing `runtime_status`, `gpu_metrics`
  with wrong revision / wrong size / truncated / unset clocks, temp labels
  swapped, missing temp, garbage number, `power1_input` fallback, no hwmon, empty
  `pp_dpm_mclk`, two cards (lowest address wins), wrong device, wrong vendor,
  not bound, no driver dir.
- Cache: same or older timestamp never re-reads; a card that starts suspended
  gets its values once awake.
- Live: idle plausibility, then a VA-API H.264 encode must push the video engine
  to ≥ 50% and vclk/dclk to ≥ 1000 MHz (got 100%, 2933 / 2200 MHz).
- Everything runs under ASan + UBSan. Checked that the suite catches bugs: three
  injected ones (power units, a `gpu_metrics` offset, the suspended check) all failed.

Meters (steps 2 to 4):

- Each meter checked against raw sysfs and `amdgpu_top` side by side:
  - idle desktop
  - game load (WoW / Starfield): usage, power, temps, clocks, VRAM
  - VRAM filling up
  - video engine: ffmpeg VA-API encode and decode, pinned to the 9070 XT's render node
- Every meter in all four modes (bar / text / graph / LED), in a narrow column,
  with °F switched on.
- htop's own CPU use about the same as stock.
- A few minutes on the `--enable-debug` build with AddressSanitizer (once, after
  step 4, with all meters in the header; the sampler alone already runs under ASan).

## Order of work

1. ~~Dev clone + `AMDGPU.c` sampler, checked against sysfs before any meter exists.~~
   Done 2026-10-28: `src/htop` on branch `amdgpu-meters` (from tag 3.5.3), one
   commit (`linux: add AMDGPU sysfs sampler for RX 9070 XT meters`). Dev build: `./configure --prefix=/usr --sysconfdir=/etc
   --enable-affinity --enable-capabilities --enable-delayacct --enable-sensors
   --enable-unicode --enable-debug && make`.
2. ~~GPU usage, VRAM, power meters.~~ Done 2026-10-28, commit `4875c09e`: `linux/AMDGPUMeter.{c,h}`
   (3 classes, modeled on `SwapMeter.c`, upstream colors `GPU_ENGINE_1`,
   `MEMORY_1`, `BATTERY`), registered after `GPUMeter_class` in
   `linux/Platform.c`. Checked live in all 4 modes against sysfs (idle and under a
   VA-API encode load) and on fake trees (`sleep`, partial `N/A`, card missing).
3. Temps and both clock meters.
4. Video engine meter.
5. `packaging/PKGBUILD`, install, rework the htop header layout.
6. Later, if wanted: video engine process list, GTT in the VRAM meter, fan RPM,
   other cards.

## Before going public

Both GitHub repos are private for now. Before making them public:

- Turn `orlfman/htop` into a real GitHub fork of htop-dev/htop (forks can't be
  private, so it's a plain repo now): fork on GitHub, push `amdgpu-meters` there,
  delete the private copy.
- Add a `LICENSE` (GPL-2.0-or-later, like htop) and a short `README.md` to htop-gpu.
- `tools/test-sampler.py`: find the card's PCI address instead of hardcoding
  `0000:04:00.0`.

## Open questions

- Meter names and captions: keep the placeholders above or rename?
- Header layout: the two columns already have 16 rows each (P cores + memory etc.
  left, E cores right). Seven GPU meters could go under the E cores, replace the
  stock GPU meter on the left, or get their own third column. Decide at step 5.
