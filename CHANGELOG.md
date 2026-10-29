# htop-gpu changelog

Newest first. One entry per agent session: date, agent, what changed, check
results, anything left half done, what's next. See `AGENTS.md` for the rules.

## 2026-10-28, Codex: CPU caption Pwr, package 3.5.3-8 installed

- Re-read the shared docs, upstream instructions/style guide, and current
  audit/release handoff. Both repositories were clean; Claude had already
  committed and installed finding 6's PL1 fix in 3.5.3-7.
- User authorized the caption change, commit, push, and installation.
  Source commit `61c598b1` (`linux: label Intel CPU power meter Pwr`) changes
  only the caption from CPU to Pwr. `IntelCPUPower` and the GPU meter's
  separate identity are unchanged; saved layouts need no edits.
- Source branch pushed. Exported nine patches and bumped pkgrel to 8;
  all checksums pass and the patches reproduce all 364 tracked source files.
  Earlier patch changes are the generated series count (8 -> 9).
- Build and full ASan/UBSan build/normal restore: zero warnings.
  `STYLE OK`; CPU and GPU sampler suites `ALL PASSED` (live CPU
  10.4/127.7 W pre-load/busy; video 100%, clocks 2933/2200 MHz).
  CPU/GPU power meters coexist as Pwr in all four modes, sanitizer clean.
- `makepkg -fC --noconfirm` built 3.5.3-8 without compiler warnings.
  Packaged captions and all 33 config-path checks passed. No stock file
  conflicts; namcap matches stock's known diagnostics apart from its old
  license warning.
- Installed 3.5.3-8 through system authentication. Verified version, exact
  installed binary match, both Pwr bars using a copy of the real layout,
  and `pacman -Qkk` (16 files, zero altered for each package).
  Stock htop and both user configs retain their baseline hashes.
- AUDIT.md records validation and limits; finding 7 stays deferred.
  This release commit includes the package metadata/patches and handoff docs.
  In progress nobody; no remaining implementation work for the rename.

## 2026-10-28, Claude Code (Claude Opus 5.5): finding 6 reviewed, committed, installed

- Reviewed Codex's PL1 fix and tests; agreed. Re-ran: build clean, `STYLE OK`,
  `test-rapl.py` `ALL PASSED`; the old code fails 7 of the new checks.
- Committed as `6c06d243` on top (crediting Codex); folding it into `363370bd`
  would need a force-push that wasn't requested, so history is unchanged.
- Package 3.5.3-7 (8 patches), installed. Codex's audit docs committed with it.

## 2026-10-28, Codex: fixed audit finding 6 (mutable Intel PL1)

- User authorized the P2 fix and deferred additional CPU-package discovery
  (finding 7). Only `src/htop/linux/IntelRAPL.c` changed in production source.
- Read the long-term power limit each newer sampler tick; removed the
  permanent `limitsRead` cache. Static energy-counter ranges remain cached
  after a successful read, with retries while unavailable. Same/older ticks
  still share the complete cached sample.
- Added stateful regressions to `tools/test-rapl.py` for changing, missing,
  malformed, unreadable, and restored limits; checks preserve correct watts
  and timestamp caching. Added missing-range recovery before a counter wrap.
  Before the production fix, seven new limit assertions failed as expected.
- After the fix: CPU and GPU sampler suites `ALL PASSED`; `STYLE OK`;
  full normal and ASan/UBSan builds in a disposable copy passed with zero
  warnings. Live CPU pre-load/load readings were 12.4/127.4 W.
- Independent production-meter callbacks now show `61.0W/65W` and
  `:61.0W limit:65W` after a 250 -> 65 W change, use N/A on failed limit
  reads, and recover correctly. All four display modes ran on the fresh
  sanitized full build without reports. Syntax/diff checks passed.
- Updated AUDIT.md with the fix, red/green evidence, testing limits, and
  deferred P3 status; PLAN.md is back to nobody in progress.
  Uncommitted: outer AUDIT.md, PLAN.md, CHANGELOG.md, tools/test-rapl.py;
  nested linux/IntelRAPL.c. Prior audit documentation was preserved.
- Existing binaries, user configs, sysfs settings, and packaging are unchanged.
  Installed 3.5.3-6 and patch 0007 still contain the previous code; commit and
  re-export are needed before a future package includes the fix.
  No install, commit, or push. Next: package/release steps only if requested.

## 2026-10-28, Codex: independent Intel CPU power audit

- Audited outer `4c631711`, htop `363370bd`, installed `htop-gpu 3.5.3-6`.
  Read the shared/upstream instructions and current plan/changelog first;
  both repositories were initially clean.
- Added AUDIT.md finding 6 (P2): a changed PL1 limit stays cached until
  rediscovery/restart. A live production-meter probe over fake counters
  retained `61.0W/250W` and `limit:250W` after PL1 changed to 65 W.
- Added finding 7 (P3): a second package appearing while the first is readable
  is never discovered; demonstrated 10 W/250 W instead of the combined
  30 W/375 W. This multi-package edge case does not affect the current
  single-package machine. Neither implementation issue was fixed.
- CPU and GPU sampler suites, config suite, and style regression suite all
  `ALL PASSED`; `STYLE OK`. CPU pre-load/load readings were 21.7/128.1 W.
  Independent live watts matched raw energy deltas; production meter
  permission/parse/range recovery checks passed under ASan/UBSan.
- Full normal and ASan/UBSan builds passed with zero warnings in a disposable
  copy. All four CPU display modes ran without sanitizer reports; seven
  patch checksums/exact source reproduction and installed integrity passed.
- Pre-report hashes: 402 files checked, only the deliberate PLAN.md marker
  differed. Uncommitted: AUDIT.md, PLAN.md, CHANGELOG.md. Source, existing
  binaries, and both user configs unchanged; no install, commit, or push.
- Full reproduction details and testing limits are in AUDIT.md; in progress
  nobody. Next: fix findings 6-7 only if requested.

## 2026-10-28, Claude Code (Claude Opus 5.5): Intel CPU power meter

- **User's request:** CPU power, Intel only for now; the user's udev rule
  (`99-rapl-read.rules`) makes the `intel-rapl:0` package counter readable.
- **`src/htop` commit `363370bd`** (`linux: add Intel CPU package power
  meter`): new `linux/IntelRAPL.{c,h}` sampler + `linux/IntelRAPLMeter.{c,h}`.
  Package power = energy delta / time between refreshes (none on the first),
  wrap-around at `max_energy_range_uj`, all `intel-rapl:N` packages summed,
  subzones and `intel-rapl-mmio` copies skipped, bar against the long term
  (PL1) limit, `no access` when the counter is root-only. Built in the audit
  lessons: discovery retried, limits retried until read, one read per refresh.
- **Tests:** new `tools/test-rapl.py` + `tools/rapl-sample.c` (ASan/UBSan):
  deltas, cache, wrap, two packages, no access → readable, counters
  appearing/disappearing, limit appearing later, garbage, all under one running
  sampler; live idle 9.2 W, all CPUs busy 127.8 W. Two injected bugs (wrap,
  access check) were caught. Meter checked in all 4 modes on the ASan htop.
- **Package 3.5.3-6** (7 patches), installed (user typed sudo). Placed under
  Swap in the htop-gpu left column, caption `CPU` (user's choices).
- **Checks:** build clean, `STYLE OK`, all suites `ALL PASSED`.

## 2026-10-28, Codex: fixed audit finding 5

- User authorized the idle-clock test correction. `tools/test-sampler.py`
  now uses a shared validator that accepts zero at idle while preserving
  missing/negative/above-peak checks and the valid peak seed requirement.
- Added a fake-sysfs 0 -> 1500 -> 0 MHz sequence under one running sampler,
  checking complete expected samples and the actual live validator, plus
  five invalid-value/peak guard cases. No production code changed.
- Checks: full sampler suite `ALL PASSED` with ASan/UBSan and live encode;
  `STYLE OK`; focused validator cases and old-comparison negative control;
  Python syntax and `git diff --check`; full build in a disposable copy with
  zero warnings. Existing binaries and user configs stayed unchanged.
- Recorded the resolution in AUDIT.md and updated PLAN.md; in progress nobody.
  Uncommitted: `tools/test-sampler.py`, `AUDIT.md`, `PLAN.md`, `CHANGELOG.md`.
  Previous audit/trace docs preserved. No install, package rebuild, commit,
  or push; htop source HEAD and installed package stay unchanged.
- Next: optional step 6 work, only if wanted.

## 2026-10-28, Codex: traced the zero-clock test failure

- Reproduced the zero on the first sample under strace: the real `freq1_input`
  read returned `"0\n"` successfully, and the unchanged sampler reported 0 MHz.
  The process exited cleanly under ASan/UBSan; no parsing/unit error observed.
- Root cause of the failure: `test-sampler.py` requires a strictly positive
  idle sclk. Filed AUDIT.md finding 5 (P2), open; no test/source fix applied.
- Matched GPU MP1 14.0.3 to Linux v7.3 SMU source: hwmon sclk uses the averaged
  gfx clock, selecting the low-utilization metric at activity <= 5%.
  The reproduced sample reported 4%. Exact GFXOFF state was not measured.
- Separate paired hwmon/gpu_metrics reads showed differing snapshots and zero
  averaged metrics; the driver aliases current_gfxclk to that same average.
  Full evidence and primary-source links are in AUDIT.md.
- Recommendation: accept nonnegative idle sclk, keep missing/negative/upper-bound
  checks, and cover zero in fake sysfs; keep workload-specific checks separate.
- Preserved existing uncommitted re-test docs. Uncommitted documentation remains
  `AUDIT.md`, `PLAN.md`, `CHANGELOG.md`; source, binaries, user configs unchanged.
- Validation: syscall trace, driver-source inspection, paired sensor reads,
  hash checks, and `git diff --check`. No full rebuild, install, commit, or push.

## 2026-10-28, Codex: independent re-test of finding 4

- Baseline: outer `cfe216f9`, htop `631bc883`, installed `htop-gpu 3.5.3-5`.
  All seven new cached-value recovery cases passed on both sampler suite runs.
- Independent production sampler/fan display probe: missing `fan1_max` then
  restored under one process now recovers to `Fan:1193RPM max:3200RPM` on the
  next newer tick. Same/older ticks remain cached; ASan/UBSan clean.
- First sampler suite run failed one live idle `sclk=0` plausibility check;
  all other checks passed. Sixty subsequent raw sensor reads had no zero;
  one full rerun passed. Cause unresolved; both outcomes are in AUDIT.md.
- Both config suites passed (33 each), style regression suite passed (7),
  `STYLE OK`, live encode passed on both runs, and all eight meters in all
  four modes ran on the existing ASan/UBSan binary without reports.
- Syntax, six patch checksums/exact source reproduction, installed integrity,
  and package coexistence checks passed. Pre-report hashes: 395 checked,
  only the deliberate PLAN.md in-progress marker changed.
- Uncommitted documentation: `AUDIT.md`, `PLAN.md`, `CHANGELOG.md`. No source,
  binary, or user config changes; no full rebuild, reinstall, commit, or push.
- Next: capture raw sensor evidence if the zero-clock live check recurs.

## 2026-10-28, Claude Code (Claude Opus 5.5): fixed audit finding 4

- Reproduced Codex's finding independently; the bug covered every value read
  once (VRAM total, mclk levels, temp limits, temp/clock labels, `fan1_max`),
  not only the fan. Fix: one-time reads count as done only when all are
  present (`AMDGPU_staticComplete()`), retried each refresh until then.
- 7 new recovery cases in `test-sampler.py` (remove + restore under one running
  sampler), all failing before the fix; display recovery shown on a fake card
  inside one htop process. `expected()` now tolerates a missing `pp_dpm_mclk`.
- Squashed into the sampler and fan commits (user's choice), force-pushed with
  lease. Old → new: `50714d79`→`6813391d`, `75dce070`→`7171bb46`,
  `0f0243a9`→`0b54b642`, `e4d2444b`→`4870d3a8`, `8717c760`→`762add8d`,
  `546413b7`→`631bc883`. Same final tree; each commit builds, 0 warnings.
- Package 3.5.3-5. All suites pass, ASan + UBSan clean, namcap as stock.
  Resolution recorded in AUDIT.md (per the AGENTS.md audit rule).
- Committed Codex's uncommitted fan-audit docs (AUDIT.md section, AGENTS.md
  audit rule, CHANGELOG/PLAN entries) together with this.

## 2026-10-28, Codex: fan audit findings recorded

- Added the fan RPM audit to `AUDIT.md`, including one open P2: a failed first
  `fan1_max` read stays cached and hides valid RPM after the file recovers.
  Reproduced under one running sampler/display probe with ASan + UBSan.
- Recorded passing sampler/live checks, 33 installed config checks, style,
  production fan state probes, all four live fan modes, patch/package integrity,
  and 395 unchanged file hashes. Physical spinning fan remains unverified.
- User's standing instruction: every future audit/re-test is recorded in
  `AUDIT.md`; added that rule to `AGENTS.md`. PLAN.md now lists the open issue.
- Documentation only. Uncommitted: `AUDIT.md`, `AGENTS.md`, `PLAN.md`, and
  `CHANGELOG.md`. No source/config changes, rebuild, install, commit, or push.
- Validation for this documentation update: content checks and `git diff --check`;
  test results above come from the completed audit and were not rerun for prose.
- Next: fix the fan maximum recovery issue when authorized; see `AUDIT.md`.

## 2026-10-28, Claude Code (Claude Opus 5.5): fan meter

- **User's request:** fan speed, aware of the card's zero RPM mode.
- **`src/htop` commit `546413b7`** (`linux: add AMD GPU fan meter`): sampler
  reads `fan1_max` with the one-time values and `fan1_input` every refresh;
  new `AMDGPUFan` meter (`Fan`, bar, `GPU_ENGINE_2` color): `Fan:1193RPM
  max:3200RPM`, and `Fan:0RPM (stopped)` / bar text `stopped` at 0 RPM. The
  start temperature of zero RPM mode is only exposed with overdrive on
  (`gpu_od/fan_ctrl`), which stays off.
- **Tests:** `test-sampler.py` checks fan values in every case plus spinning,
  `fan1_input` missing, `fan1_max` missing, and a live 0..max plausibility
  check. On the ASan build: live `stopped`, fake 1193 RPM (bar 37%), missing →
  `N/A`, suspended → `sleep`, LED renders; no sanitizer reports.
- **Package 3.5.3-4** (6 patches), installed (user typed sudo). Fan added after
  VCN in `~/.config/htop-gpu/htop-gpurc` (backup `htop-gpurc.bak-2026-10-28`).
- **Checks:** build clean, `STYLE OK`, sampler and config-path suites
  `ALL PASSED`. Not yet seen live: the fan spinning (needs a game).

## 2026-10-28, user + Claude Code (Claude Opus 5.5): game-load check

- The user ran `htop-gpu` 3.5.3-3 next to Dune: Awakening with MangoHud; the
  screenshots are in `docs/game-load-test/`. All meters agree with MangoHud:
  GPU 100% vs 99%, VRAM 7.19G vs 7.2 GiB, temps 56/73/68 °C exactly equal, GPU
  clock 2964 vs 2957 MHz, VRAM clock 1258 MHz both, VCN 0% (not recording).
  Power 282 W vs 302 W, most likely the two tools reading at different moments.
- Still not seen live: GPU clock above the 3000 MHz bar seed (peak was 2964;
  the clock meter is text in the user's layout anyway) and the yellow/red
  temperature colors (junction 73 °C, threshold 90). Both are covered by the
  fake-card tests.
- This closes the "not covered by either agent" item from Codex's re-test.

## 2026-10-28, Codex: independent re-test of the audit fixes

- Recorded in `AUDIT.md` ("Independent re-test by Codex"; status line updated),
  committed by Claude Code at the user's request. Codex changed no other files.
- All three findings pass on outer `6efbb1c` / htop `8717c760`: config-path suite
  (33) on the dev and installed binaries, sampler suite incl. the four recovery
  cases, style-check suite (7) plus `STYLE OK`; patch checksums and
  byte-for-byte patch application, no shared files with stock htop,
  `pacman -Qkk` clean. No new findings.
- Not covered by either agent yet: the meters under a real game load (sclk
  above the 3000 MHz seed, high VRAM, temps near the color thresholds).

## 2026-10-28, Claude Code (Claude Opus 5.5): fixed Codex's audit findings

- **Codex audit** (`AUDIT.md`, by Codex, read-only audit): 3 P2 findings. Each
  reproduced independently first, then a regression test that failed on the
  audited code, then the fix. Details in AUDIT.md's Resolution section.
- **1. Seeding from read-only / symlinked stock configs** → stock files read
  with `checkWritability` off (`Settings.c`). `test-config-path.sh` 16 → 33 checks.
- **2. Discovery never recovered** → card looked for again while missing and
  after its driver link disappears; hwmon re-searched until found and when it
  goes away (`linux/AMDGPU.c`). 4 recovery cases in `test-sampler.py` under one
  running sampler.
- **3. Style check passed with broken tools** → tool presence check, IWYU
  `--error=3` exit codes, astyle failure = tool failure; exit 0/1/2. New
  `tools/test-check-style.sh`.
- **History rewrite (user's choice):** fixes squashed into their commits with
  `amend!` commits + `git rebase --autosquash`, force-pushed with lease.
  Old → new: `0c74a6b7`→`50714d79`, `4875c09e`→`75dce070`, `f45e9ec7`→`0f0243a9`,
  `fe388c80`→`e4d2444b`, `7d510f17`→`8717c760`. Older entries below still name
  the old hashes. Final tree = pre-squash tip; each commit builds, 0 warnings.
- **Installed** `htop-gpu 3.5.3-3` (user typed sudo); checked on the real
  config, which stayed unchanged; `pacman -Qkk` clean; stock htop untouched.
- **Checks:** build clean, `STYLE OK`, all three suites `ALL PASSED`, ASan +
  UBSan run (config-path suite + live meters) with no reports.

## 2026-10-28, Claude Code (Claude Opus 5.5): own config, side by side with stock htop

- **User's request:** htop-gpu gets its own config in an XDG folder named
  `htop-gpu`, file `htop-gpurc`, and installs next to stock htop. The user
  explicitly OK'd diverging from upstream for this.
- **`src/htop` commit `7d510f17`** (`Settings: give htop-gpu its own
  configuration file`): `~/.config/htop-gpu/htop-gpurc` (or under
  `$XDG_CONFIG_HOME`). Without one yet it starts from stock's
  `~/.config/htop/htoprc`, then `~/.htoprc`, and saves that as its own; stock
  files are only read. Found while reading: upstream moves and **deletes**
  `~/.htoprc`, which htop-gpu would have done to stock htop's file, so that
  block is replaced. `$HTOPRC` and `/etc/htoprc` work as before. Man page
  updated.
- **New `tools/test-config-path.sh`:** 16 checks in throwaway homes (fresh,
  seeded from stock, own file wins, legacy not deleted, XDG, `$HTOPRC`). All
  pass; the unpatched build fails 7, so the test can tell. `htop-capture.py`
  learned `-` (leave `HTOPRC` unset).
- **Package `3.5.3-2`:** installs as `htop-gpu` (binary, man page, desktop entry
  with Name/Icon/Exec, icons renamed), no `provides`/`conflicts`, and fails the
  build if a file named like stock htop's is left over. 0 files shared with the
  stock package; namcap as for stock.
- **User's files:** current GPU layout copied to
  `~/.config/htop-gpu/htop-gpurc`, then `~/.config/htop/htoprc` restored from
  `htoprc.bak-2026-10-28` (two columns with the stock GPU meter), in that order,
  so the first htop-gpu start couldn't seed from the restored file.
- **Installed** (user typed sudo, confirmed both): `htop-gpu 3.5.3-1 → 3.5.3-2`,
  then repo `htop 3.5.3-1.1`. Checked: `htop` = `3.5.3-1.1-arch` with two
  columns, `htop-gpu` = `3.5.3-2-gpu` with the GPU column, neither run changed
  its config file.
- **Checks:** build clean, `STYLE OK`, `ALL PASSED` (sampler + config path).

## 2026-10-28, Claude Code (Claude Opus 5.5): step 5

- **Packaging:** `packaging/PKGBUILD` (Arch's htop PKGBUILD as `htop-gpu`,
  provides/conflicts `htop`, SPDX `GPL-2.0-or-later`, version `3.5.3-1-gpu`)
  plus the 4 commits as patches from new `tools/export-patches.sh`. The git
  source checksum equals Arch's for 3.5.3. Built with the user's makepkg.conf
  (`-march=arrowlake-s`), zero warnings, same file list as stock htop.
- **Found and fixed:** the first build linked libunwind (installed here, absent
  from Arch's chroot, so stock htop doesn't link it) → `--without-libunwind`.
  `namcap` now matches the stock package's report.
- **Installed** (user's OK, user typed sudo + confirmed): `sudo pacman -U` removed
  `htop 3.5.3-1.1` and installed `htop-gpu 3.5.3-1`; `/usr/bin/htop --version` =
  `3.5.3-1-gpu`. Packaged binary checked with all 7 meters against sysfs first.
- **Header** (user's choices): `three_33_34_33`, P cores | E cores | GPU column
  (GPU/VRM/Pwr/VCN bars, temps/clocks text), stock GPU meter removed, captions
  kept. Backed up as `~/.config/htop/htoprc.bak-2026-10-28`; edited with htop
  not running; previewed with the installed binary on a copy.
- **New:** `tools/check-upstream.sh` (PKGBUILD / installed / repo / upstream
  versions; currently "up to date", 3.5.3 everywhere).
- **AGENTS.md:** htoprc rule relaxed to "only when the user asks, back up, htop
  not running"; reinstalling htop-gpu needs the user's OK; packaging workflow.
- **Committed and pushed** (user's OK): `packaging/` (PKGBUILD + 4 patches), the
  two new tools and the doc changes, in one htop-gpu commit. `src/htop` unchanged.
- **Next:** optional step 6 items (video engine process list, GTT, fan, other
  cards) and the "Before going public" list.

## 2026-10-28, Claude Code (Claude Opus 5.5): step 4

- **Meter:** `AMDGPUVideo` (`VCN:100% vclk:2933MHz dclk:2200MHz`) in
  `linux/AMDGPUMeter.c`, bar by default like GPU usage, `GPU_ENGINE_4` color
  (bold blue). One busy % for encode and decode, since RDNA 4 shares one queue.
  Registered with one more line in `linux/Platform.c`. All 7 meters now exist.
- **Live checks** (`htop-capture.py`): idle 0% / 25 / 25 MHz, encode 99% /
  2933 / 2200 MHz, decode 100% / 2933 / 2200 MHz with GPU usage at 5% (the load
  lands on the right meter); all equal to sysfs at the same moment. Graph and LED
  render.
- **Fake checks:** suspended → `sleep`; `gpu_metrics` revision 1.4 → busy shown,
  `vclk:N/A dclk:N/A`; missing `vcn_busy_percent` → `N/A`.
- **Sanitizers:** new `tools/build-htop-asan.sh`. Whole htop under ASan + UBSan,
  all 7 meters, all 4 modes: 30 s live under encode load, then fake suspended,
  hot, broken (4 missing files, garbage, truncated `gpu_metrics`) and unbound
  trees. Zero reports; positive control confirmed logging works. Normal binary
  rebuilt afterwards (no sanitizer symbols, no fake path).
- **Checks:** build clean, `STYLE OK`, `ALL PASSED`.
- **Committed and pushed** (user's OK): `src/htop` commit `fe388c80` (`linux: add
  AMD GPU video engine meter`) and the doc/tool changes here.
- **Next:** step 5, PKGBUILD in `packaging/`, install (ask first), header
  layout. Captions and the layout are still open questions (PLAN.md).

## 2026-10-28, Claude Code (Claude Opus 5.5): step 3

- **Meters:** `AMDGPUTemp` (`GPU temp: edge:41°C junction:43°C mem:42°C`),
  `AMDGPUClock` (`GPU clock: 1487MHz`) and `AMDGPUMemClock`
  (`VRAM clock: 772MHz 12.4Gbps busy:0%`) in `linux/AMDGPUMeter.c`, text mode by
  default with upstream's text-meter captions. Bar/graph: junction vs its limit,
  sclk vs highest seen (seed 3000), mclk vs its top level. Registered with three
  more lines in `linux/Platform.c`.
- **Temperature colors:** green / yellow (crit − 20) / red (crit − 10) per
  sensor, bar follows the junction (attribute switching as in `LoadMeter`).
  Honors htop's °F setting. Temps are printed with `%.0f`, not an `(int)` cast,
  so garbage sysfs values can't overflow.
- **Live checks:** all 4 modes; values match sysfs idle and under a 4K encode
  (43/46/44 °C, 1563 vs 1560 MHz, 772 MHz, busy 3%); °F shows 109/115/111.
- **Fake checks** (new `tools/htop-capture.py` shows colors): edge 50 green,
  junction 95 bold yellow, mem 100 bold red, bar yellow; suspended → `sleep`;
  missing mem temp → `mem:N/A` only; missing mclk + garbage busy →
  `N/A busy:N/A`; missing junction → bar `N/A`, text keeps edge/mem; unbound →
  `N/A`. Fixed: a missing temp showed `N/A` in green, now plain value color.
- **Style:** IWYU wanted `Settings.h`. astyle flattens `case` labels unlike most
  upstream code, so the color switch is an `if` chain (as in `LoadMeter`); noted
  in PLAN.md.
- **Tool fix:** `build-htop-fake.sh` now does a normal build first. Before, a
  meter source edited just before a fake build got compiled with the fake
  `CPPFLAGS`, leaving the fake path in the normal binary's debug info
  (harmless, `-ggdb3` macro record, but not what the script promises).
- **Checks:** build clean, `STYLE OK`, `ALL PASSED`; normal binary has no fake path.
- **Committed and pushed** (user's OK): `src/htop` commit `f45e9ec7` (`linux: add
  AMD GPU temperature and clock meters`) and the doc/tool changes here.
- **Open:** captions in bar mode (`GPU`, `GPU`, `VRA`), see PLAN.md.
- **Next:** step 4, video engine meter.

## 2026-10-28, Claude Code (Claude Opus 5.5): step 2

- **Meters:** new `linux/AMDGPUMeter.{c,h}` with `AMDGPUUsage` (`GPU`),
  `AMDGPUVRAM` (`VRM`) and `AMDGPUPower` (`Pwr`), modeled on upstream's
  `SwapMeter.c`, reusing upstream colors. Registered with one include and three
  lines after `GPUMeter_class` in `linux/Platform.c`, plus two `Makefile.am`
  lines. Missing values show `N/A`, a sleeping card shows `sleep`.
- **Caption change:** VRAM's caption is `VRM` because bar/graph modes only draw
  3 caption characters (upstream's convention). Names are still open (PLAN.md).
- **Live checks** (dev build, `HTOPRC=test/...`): bar, text, graph and LED all
  render; values match sysfs at idle and under a 4K VA-API encode (16% busy,
  55 W, 1.31G VRAM). The stock GPU meter read 108.9% at the same moment.
- **Fake-card checks:** new `tools/fake-sysfs.py` + `tools/build-htop-fake.sh`.
  Suspended → `sleep` everywhere; garbage busy + missing cap → `N/A` on just those
  two; unbound card → `N/A`, graphs flat, no assert in the debug build.
- **Checks:** build clean, `STYLE OK` (IWYU wanted `<stddef.h>` added and
  `Machine.h` dropped, since `Meter.h` provides it), `ALL PASSED`.
- **Committed and pushed** (user's OK): `src/htop` commit `4875c09e` (`linux: add
  AMD GPU usage, VRAM and power meters`) and the doc/tool changes here.
- **Next:** step 3, temperatures and both clock meters.

## 2026-10-28, Claude Code (Claude Opus 5.5): GitHub setup

- Installed `github-cli` (user ran the sudo part) and logged in as `orlfman` with
  the browser device flow; token in the system keyring, git uses
  `gh auth git-credential` for github.com.
- Created two private repos and pushed: `orlfman/htop-gpu` (this folder, `main`)
  and `orlfman/htop` (`src/htop`, branch `amdgpu-meters`, set as default). In
  `src/htop` the htop-dev remote is now `upstream`, and `origin` is `orlfman/htop`.
- AGENTS.md / PLAN.md updated: remotes, push only when asked, `git fetch upstream`,
  and a "Before going public" checklist.
- No code changes. Next: still step 2.

## 2026-10-28, Claude Code (Claude Opus 5.5)

Planning, step 1, and setting the project up for more than one agent.

- **Plan:** `PLAN.md` written from measurements on the card (sysfs, hwmon,
  `gpu_metrics`). A VA-API encode and decode test showed RDNA 4 reports both on
  one video queue, so there is one combined video engine meter.
- **Step 1, `src/htop` commit `0c74a6b7`** (`linux: add AMDGPU sysfs sampler for
  RX 9070 XT meters`): `linux/AMDGPU.{c,h}` + `Makefile.am` entries. Found and
  fixed during testing: the one-time reads at startup could wake a
  runtime-suspended card, so they now wait until the card is seen awake.
- **Tools:** `tools/test-sampler.py` (exact match on a frozen sysfs copy, 17
  broken-tree cases, cache, wake-up, live VA-API load, ASan/UBSan) with its
  driver `amdgpu-sample.c` / `build-sampler.sh`; `tools/check-style.sh` (IWYU with
  upstream's mapping + upstream's astyle baseline, on htop-gpu's own files only).
- **Upstream alignment:** reviewed against `docs/styleguide.md`; IWYU cleanup
  (added `<stdint.h>`, `<sys/types.h>`, dropped unneeded `<stddef.h>`).
- **Collaboration setup:** `AGENTS.md` (shared rules, turn-taking, checks),
  `CLAUDE.md` importing it, this changelog, project folder made a git repo
  (`src/`, `test/` and makepkg output ignored). Packaging moved to `packaging/` in
  the plan so makepkg's `src/` can't collide with the dev clone. Git identity
  `orlfman` with the GitHub noreply address, set per repo.
- **Checks:** build clean, `STYLE OK`, `ALL PASSED`.
- **Left open:** meter names/captions and header layout (PLAN.md open questions).
- **Next:** step 2, GPU usage, VRAM and power meters in `linux/AMDGPUMeter.{c,h}`.
