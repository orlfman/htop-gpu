# htop-gpu: plan

Status (2026-10-29): steps 1–5 done. `amdgpu-meters` = `6813391d` sampler,
`7171bb46` GPU usage / VRAM / power, `0b54b642` temperatures and clocks,
`4870d3a8` video engine, `762add8d` own config file, `631bc883` fan meter,
`363370bd` Intel CPU power, `6c06d243` PL1 refresh, `61c598b1` CPU Pwr caption,
`bb4f7331` Intel iGPU meters, `44265679` AMD GPU heading, `798d8cfa` CPU heading;
all pushed. htop-gpu 3.5.3-13 is installed as `htop-gpu` next to the repo `htop`, each with its own
config (`~/.config/htop-gpu/htop-gpurc` with the GPU column, `~/.config/htop/htoprc`
two columns). All five audit findings are fixed; findings 1-4 were
independently re-tested, and Codex validated the finding 5 idle-clock test
fix with zero-clock and invalid-reading regressions. See AUDIT.md.
Intel PL1 staleness (finding 6) is fixed in `6c06d243`, first installed in
3.5.3-7 and retained in 3.5.3-8; finding 7 (P3, later CPU packages) is deferred at the user's
request. The [Intel iGPU baseline](PLAN-INTEL-IGPU.md) is implemented, tested,
and installed: visible-app utilization, requested clock, approximate allocated memory,
and combined video encode/decode. The revised plan was committed and pushed
first as outer `b145c766`. Claude Code reviewed the implementation on 2026-10-29
and committed it as `bb4f7331`; the re-exported patch 0010 has the same code
the installed 3.5.3-12 was built from.
Build, style, stateful fake tests/negative controls, pinned live Intel workloads,
existing regression suites, and full sanitized meter checks passed; see AUDIT.md
for results and remaining real suspend/Mission Center comparison limits.
Installed 3.5.3-12 passes integrity checks and matches the tested package binary.
The Intel clock/memory readouts now show just MHz and memory amount at the user's
request; requested-clock/allocation semantics remain in the meter descriptions.
The normal heading is now just `Intel iGPU`, with sleep/access/error indications
retained; visible-app scope remains in the meter descriptions.
The user's actual third column now has Intel below the eight AMD rows, with
spacer/heading/four stats (fourteen rows). Config backup:
`~/.config/htop-gpu/htop-gpurc.bak-2026-10-29_14-47-46`.
Stock htop and its config are unchanged. Next: commit/push the implementation and
release records when requested, plus remaining idle-PM/reference comparisons.
Extra Intel engine rows remain deferred.
Finding 8 (P2) is fixed and validated in 3.5.3-12. Known Intel client ownership
is tracked by PID/starttime/FD, so access loss reports unavailable rather than
false zero; shared aliases, exits, reuse, and unrelated denials remain correct.
All 18 stateful fake groups/three negative controls passed; the old source fails
ten new assertions. Full sanitized meter transitions and package checks passed.
No new GPU load tests; real PM/reference comparison limits remain. See AUDIT.md.

Latest full patch audit (2026-11-10, Codex): source `798d8cfa`, package 3.5.3-13.
No new actionable runtime defect confirmed. All exported patches and checksums
match the source. Finding 14 (P3) is fixed in the heading test, which passes all
25 checks with `NO_COLOR` set or unset. Build, style, and AMD sampler checks
also passed after the fix. See AUDIT.md for evidence and limits.

Local package rebuilt and verified (2026-11-10, Codex) at
`packaging/builds/cc2f286/htop-gpu-3.5.3-13-x86_64.pkg.tar.zst`.
Its executable matches the installed 3.5.3-13 build. See AUDIT.md for checks.

[AMD meters on RDNA 2+ dedicated cards](PLAN-AMD-DGPU.md): done 2026-11-11
(Claude Code). htop `f842f486`, patch 0013, package 3.5.3-14 built and checked at
`packaging/htop-gpu-3.5.3-14-x86_64.pkg.tar.zst` and **installed** 2026-11-11
(replacing 3.5.3-13). Pushed 2026-11-11. See the CHANGELOG entry for what differs
from the plan, AUDIT.md for the package checks.

RDNA 2+ audit (2026-11-11, Codex): identified two findings in 3.5.3-14 — 15 (P2),
sensor-directory access errors can permanently suppress cached sensors after
access returns; 16 (P3), an initial clock-scale read failure is not retried once
a current clock has been sampled. Both reproduced; build/style and all existing
AMD/heading tests pass. Patches and installed files match the reviewed source.
See AUDIT.md. Both fixed 2026-11-11 (Claude Code): htop `7c2fe84b`, patch 0014,
package 3.5.3-15, **installed**. Pushed 2026-11-11. Independently verified by Codex
2026-11-11: both fixes confirmed, no new actionable findings. The original
probes and additional error/recovery cases pass; the new tests reject the old
source. Build/style, 169 sampler and 25 heading assertions pass; patch and
installed-file integrity verified. See AUDIT.md.

Full project audit (2026-11-11, Codex), source `7c2fe84b`, package 3.5.3-15:
identified three findings — 17 (P2), AMD samples on unknown/transitional runtime state;
18 (P3), upstream checker requires an undocumented developer clone; 19 (P3),
mode docs omit Intel memory's text/LED restriction. All existing suites and
additional whole-program sanitizer/static-analysis checks passed. Installed
files match the archive and coexist with stock htop. Findings 15/16 remain fixed.
See AUDIT.md for evidence and limits. All three fixed 2026-11-11 (Claude Code):
htop `943464c0`, patch 0015, package 3.5.3-16, **installed**. Pushed 2026-11-11.
Independently verified 2026-11-11 (Codex): all three resolved under the documented
power-state compatibility policy; no new actionable findings. Original/extra
FIFO probes, old-source negative controls, 231 test assertions and real GitHub
fallback pass. Patches and installed files match the reviewed source. See AUDIT.md.

Planned next: the rest of [AMD meters for any AMD GPU](PLAN-AMD-AGNOSTIC.md)
(APUs, older cards, card selection).

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
- **Style check:** `tools/check-style.sh` must print `STYLE OK` (exit 0; 1 means
  findings, 2 means a tool is missing or failed, checked by
  `tools/test-check-style.sh`). It runs
  include-what-you-use with upstream's `iwyu/htop.imp` mapping and upstream's
  astyle baseline (`astyle -n -xb -s3 -p -xg -c -k1 -W1 -H`, shown as a diff,
  files untouched). It only checks the files htop-gpu adds on top of the upstream
  tag: upstream's own files aren't fully IWYU / astyle clean in 3.5.3 (e.g.
  `linux/GPU.c`), and fixing them would only make rebasing harder.
  One known mismatch: the astyle baseline puts `case` labels flush with
  `switch`, while most upstream code indents them (38 vs 12 in 3.5.3). Prefer
  constructs that avoid the conflict (step 3 uses an `if` chain, like
  `LoadMeter`).
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
| 4 | Temps | `AMDGPUTemp` | `GPU temp: ` | hwmon `temp1/2/3_input` + `_crit` | `GPU temp: edge:52°C junction:68°C mem:70°C` | junction vs its crit, bar text `68°C` |
| 5 | GPU clock | `AMDGPUClock` | `GPU clock: ` | hwmon `freq1_input` (sclk) | `GPU clock: 2950MHz` | vs highest clock seen (seed 3000) |
| 6 | VRAM clock | `AMDGPUMemClock` | `VRAM clock: ` | hwmon `freq2_input` (mclk) + `mem_busy_percent` | `VRAM clock: 1258MHz 20.1Gbps busy:12%` | vs top level (1258 MHz), bar text `1258MHz 20.1Gbps` |
| 7 | Video engine | `AMDGPUVideo` | `VCN` | `vcn_busy_percent` + `gpu_metrics` vclk/dclk | `VCN:100% vclk:2933MHz dclk:2200MHz` | 0–100%, bar text `100%` |
| 8 | Fan | `AMDGPUFan` | `Fan` | hwmon `fan1_input` / `fan1_max` | `Fan:1193RPM max:3200RPM`, `Fan:0RPM (stopped)` | vs max, bar text `1193RPM` / `stopped` |
| 9 | CPU power (Intel) | `IntelCPUPower` | `Pwr` | powercap `intel-rapl:N` package `energy_uj` deltas / long term limit | `Pwr:61.3W limit:250W` | vs PL1, bar text `61.3W/250W`; `no access` if root-only |
| 10 | AMD GPU heading | `AMDGPUInfo` | card name (`AMD GPU` if none) | card table `name` | `Radeon RX 9070 XT`, `Radeon RX 9070 XT: sleep`, `AMD GPU: N/A` | text only |
| 11 | CPU heading | `IntelCPUInfo` | CPU model name (`CPU` if none) | `/proc/cpuinfo` `model name`, read once, without `(R)` / `(TM)` / ` @ GHz` | `Intel Core Ultra 7 270K Plus` | text only |

Each one is a separate meter, so it can be placed, moved and switched between
bar / text / graph / LED in F2 Setup like any built-in meter. The exceptions are the
headings (`AMDGPUInfo`, `IntelCPUInfo` and the Intel iGPU's `IntelGPUInfo`), which
are text only, and `IntelGPUMemory`, which is text / LED only because the iGPU has
no whole-device memory total to scale a bar or graph against (finding 19). Captions and names
are placeholders until we settle them. All 11 rows are built (steps 2–4; fan, CPU power and
the two headings later) and show the real output. The headings work like the Intel iGPU
one (`IntelGPUInfo`): text-only meters whose caption comes from `getCaption`, as
upstream's `DynamicMeter` does.

Caption rule (upstream): bar and graph modes draw only the first 3 characters of
a caption, so bar-mode meters use 3-character captions (`Mem`, `Swp`, `GPU`),
and text mode is `caption` + `:` + values from the meter's display function.
That's why VRAM is `VRM`, not `VRAM` (which a bar would cut to `VRA`).
Text-mode meters follow upstream's other convention (`Load average: `,
`Tasks: `): a readable caption ending in `: `, values as `label:value`. Temps
and both clocks are text by default, so in bar or graph mode their captions get
cut to `GPU`, `GPU` and `VRA`, like upstream's `Battery: ` becomes `Bat`.
When a value is missing the meter shows `N/A`, and `sleep` when the card is
runtime suspended.

Temperature colors: each reading is green, yellow from 20 °C below that sensor's
critical limit, red from 10 °C below (junction 90 / 100 °C, mem 88 / 98 °C). The
bar takes the junction's color, switching attributes the way upstream's
`LoadMeter` does. Temps follow htop's °C/°F setting.

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
  PLAN-INTEL-IGPU.md         separate Intel iGPU feasibility/design/validation plan
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
    htop-capture.py          header text grouped by color (for checking colors)
    build-htop-asan.sh       whole htop with ASan + UBSan (optionally on fake-sysfs)
    export-patches.sh        amdgpu-meters commits → packaging/*.patch + checksums
    check-upstream.sh        is a newer htop out than the one htop-gpu is built on?
    test-check-upstream.sh   check-upstream.sh with and without src/htop, offline
    test-config-path.sh      own htop-gpurc, seeding (incl. read-only/symlinked stock), 33 checks
    test-check-style.sh      check-style.sh fails on findings (1) and broken tools (2)
    rapl-sample.c            test driver for linux/IntelRAPL.c
    test-rapl.py             CPU package power: fake powercap trees + live idle/busy
    gpu_metrics.py           gpu_metrics v1.3 decoder
    vcn_probe.py             runs a command, samples fdinfo + gpu_metrics
```

Dev loop:

- `./autogen.sh && ./configure <Arch's flags> --enable-debug && make` inside `src/htop`
- Run with `HTOPRC=<project>/test/htoprc ./htop` so the real
  `~/.config/htop/htoprc` never gets rewritten by a test build.

Package:

- `pkgname=htop-gpu`, installed **next to** the stock `htop` package (since
  `3.5.3-2`): `package()` renames everything stock htop also installs
  (`/usr/bin/htop-gpu`, `htop-gpu.1` man page, `htop-gpu.desktop` with
  Name/Icon/Exec changed, `htop-gpu` icons) and fails if a file named like stock
  htop's is left over. No `provides`/`conflicts`. `3.5.3-1` replaced htop
  instead.
- Own config: commit `762add8d` makes htop-gpu read
  `~/.config/htop-gpu/htop-gpurc` (`$XDG_CONFIG_HOME/htop-gpu/htop-gpurc`).
  Without one yet it starts from stock htop's `~/.config/htop/htoprc`, then
  `~/.htoprc`, and saves that as its own. Stock files are only read, never
  changed: upstream's code moves and deletes `~/.htoprc`, which htop-gpu must
  not do to stock htop's file. `$HTOPRC` still overrides. The man page says so.
  The user explicitly OK'd this divergence from upstream (2026-10-28).
- Same upstream git tag as Arch, plus the 4 `amdgpu-meters` commits as patch
  files. `tools/export-patches.sh` writes them with `git format-patch` and
  updates `_patches` and the checksums. The git source checksum `updpkgsums`
  computes equals Arch's for htop 3.5.3 (`a4619a14…`), so the base is
  byte-identical to upstream's tag.
- `--without-libunwind`: configure picks libunwind up from any build machine that
  has it (this one does), while Arch's clean chroot doesn't, so stock htop
  doesn't link it. Pinned off to match. With that, `namcap` reports exactly what
  it reports for the stock package (minus stock's old `GPL` license string).
- Same configure flags as Arch: affinity, capabilities, delayacct, sensors,
  unicode. Arch also passes `--enable-openvz` and `--enable-vserver`, but 3.5.3's
  configure no longer knows them and ignores them, so ours drops them.
- Version string `3.5.3-1-gpu`, so `htop --version` shows it's the patched build.
- `makepkg` uses `~/.config/pacman/makepkg.conf` (arrowlake-s flags, `BUILDDIR=/tmp/makepkg`).
- The PKGBUILD lives in `packaging/`, not the project root: without `BUILDDIR` /
  `SRCDEST`, makepkg unpacks into `src/` and clones into `htop/` next to the
  PKGBUILD, and `src/` would collide with the dev clone.
- Build with `makepkg -fC` in `packaging/`, install with
  `sudo pacman -U packaging/htop-gpu-<ver>-x86_64.pkg.tar.zst`. Stock htop
  stays a normal repo package that `pacman -Syu` keeps updated.

Removing it: `sudo pacman -R htop-gpu`; stock htop and its `htoprc` are
unaffected, and `~/.config/htop-gpu/` can be deleted by hand.

Updates: `pacman -Syu` updates stock htop but never htop-gpu. `tools/check-upstream.sh` shows the PKGBUILD's version, the
installed htop-gpu, the repo htop and the newest upstream tag, and says when a
newer htop is out. When htop bumps: rebase `amdgpu-meters` (see "Staying close
to upstream"), run the checks, update `pkgver` (reset `pkgrel=1`), run
`tools/export-patches.sh`, then build and install.

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
- Idle GPU clock: zero, positive, then zero under one running sampler; the
  shared live validator accepts zero and still rejects missing, negative,
  above-peak, and invalid-peak values (audit finding 5).
- Recovery inside ONE running sampler (added for AUDIT.md finding 2): hwmon
  missing at start then appearing, hwmon renumbered, card bound only after start,
  card unbound and rebound; each must match the full expected sample.
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
- ~~A few minutes on the `--enable-debug` build with AddressSanitizer.~~ Done
  2026-10-28 with `tools/build-htop-asan.sh` (whole htop with ASan + UBSan):
  all 7 meters in all 4 modes, 30 s on the live card under encode load, then 5 s
  per layout on fake suspended / hot / broken (missing files, garbage, truncated
  `gpu_metrics`) / unbound trees. Zero sanitizer reports; a positive control
  confirmed the log files get written when there is something to report.

## Order of work

1. ~~Dev clone + `AMDGPU.c` sampler, checked against sysfs before any meter exists.~~
   Done 2026-10-28: `src/htop` on branch `amdgpu-meters` (from tag 3.5.3), one
   commit (`linux: add AMDGPU sysfs sampler for RX 9070 XT meters`). Dev build: `./configure --prefix=/usr --sysconfdir=/etc
   --enable-affinity --enable-capabilities --enable-delayacct --enable-sensors
   --enable-unicode --enable-debug && make`.
2. ~~GPU usage, VRAM, power meters.~~ Done 2026-10-28, commit `7171bb46`: `linux/AMDGPUMeter.{c,h}`
   (3 classes, modeled on `SwapMeter.c`, upstream colors `GPU_ENGINE_1`,
   `MEMORY_1`, `BATTERY`), registered after `GPUMeter_class` in
   `linux/Platform.c`. Checked live in all 4 modes against sysfs (idle and under a
   VA-API encode load) and on fake trees (`sleep`, partial `N/A`, card missing).
3. ~~Temps and both clock meters.~~ Done 2026-10-28, commit `0b54b642`:
   `AMDGPUTemp`, `AMDGPUClock`, `AMDGPUMemClock` added to `linux/AMDGPUMeter.c`
   and registered after the step 2 meters. Checked live in all 4 modes, in °F,
   idle and under load against sysfs, colors with `tools/htop-capture.py` on fake
   hot temps, and `sleep` / partial `N/A` / missing card on fake trees.
4. ~~Video engine meter.~~ Done 2026-10-28, commit `4870d3a8`: `AMDGPUVideo`
   (`VCN`, bar by default, `GPU_ENGINE_4` color). Live: matches sysfs idle
   (0%, 25/25 MHz), during an encode (99%, 2933/2200 MHz) and a decode (100%
   while GPU usage read 5%). Fake: `sleep`, unknown `gpu_metrics` revision →
   `vclk:N/A dclk:N/A`, missing `vcn_busy_percent` → `N/A`. Then the full
   ASan + UBSan run with all 7 meters (see Test plan): no findings.
5. ~~`packaging/PKGBUILD`, install, rework the htop header layout.~~ Done
   2026-10-28. htop-gpu 3.5.3-1 built and
   installed in place of the repo htop (user's OK). The user chose the header:
   `three_33_34_33` with P cores | E cores | a GPU column (usage, VRAM, power,
   video as bars; temps, GPU clock, VRAM clock as text), the stock GPU meter
   removed, captions kept. Previous htoprc saved as
   `~/.config/htop/htoprc.bak-2026-10-28`.
   Then (user's request, same day): own config file and side by side. Commit
   `762add8d` (`Settings: give htop-gpu its own configuration file`) and
   htop-gpu `3.5.3-2` installed as `htop-gpu` next to the repo `htop`. The GPU
   layout moved to `~/.config/htop-gpu/htop-gpurc`, and stock `htoprc` went back
   to the two-column backup. Checked with `tools/test-config-path.sh` (16
   checks; the unpatched build fails 7 of them, including deleting
   `~/.htoprc`).
6. Later, if wanted: video engine process list, GTT in the VRAM meter, other
   cards. ~~Fan RPM~~ done 2026-10-28, commit `631bc883`: `AMDGPUFan` (row 8),
   added after VCN in the user's htop-gpu column. Zero RPM mode shows as
   `stopped`; the temperature where the fan starts is only exposed with
   overdrive enabled (`gpu_od/fan_ctrl`), which stays off.

## Before going public

Both GitHub repos are private for now. Before making them public:

- Turn `orlfman/htop` into a real GitHub fork of htop-dev/htop (forks can't be
  private, so it's a plain repo now): fork on GitHub, push `amdgpu-meters` there,
  delete the private copy.
- Add a `LICENSE` (GPL-2.0-or-later, like htop) to htop-gpu. (`README.md` added 2026-10-29.)
- `tools/test-sampler.py`: find the card's PCI address instead of hardcoding
  `0000:04:00.0`.

## Open questions

None right now. Settled 2026-10-28: captions stay as in the meters table; the
header is a third column for the GPU (see step 5).
CPU package power uses `Pwr` in the CPU column, as requested by the user;
the separate GPU power meter also uses `Pwr` in the GPU column.
