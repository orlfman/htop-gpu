# htop-gpu changelog

Newest first. One entry per agent session: date, agent, what changed, check
results, anything left half done, what's next. See `AGENTS.md` for the rules.


## 2026-11-11, Claude Code (Claude Fable 5.2): fix audit findings 17, 18 and 19

- 17: `linux/AMDGPU.c` only reads a card known to be awake. New
  `AMDGPU_powerState()` and status `AMDGPU_UNAVAILABLE`: `active`, `unsupported`
  or no `runtime_status` file → read; `suspended` / `suspending` / `resuming` →
  sleep; anything else or an unreadable status → N/A with the card name kept.
  The meter file is unchanged.
- 18: `tools/check-upstream.sh` works from a fresh clone (falls back to htop's
  GitHub URL without `src/htop`), new `tools/test-check-upstream.sh`.
- 19: README and PLAN say `IntelGPUMemory` is text / LED only.
- 17 and 18 reproduced as failing tests first. Build without warnings,
  `STYLE OK`, `test-sampler.py` 198, `test-headings.py` 27,
  `test-check-upstream.sh` 6, all ALL PASSED. Details and limits in AUDIT.md.
- Committed, packaged and installed at the user's request: htop `943464c0`
  (`linux: read an AMD card only when it is known to be awake`, a new commit),
  patch 0015, pkgrel 16. Installed `/usr/bin/htop-gpu` is byte-identical to the
  package's and shows the AMD meters live. The outer commit also carries
  Codex's two uncommitted audit records.
- Not pushed (not asked for). Next: push when the user says so; then the rest
  of PLAN-AMD-AGNOSTIC.md.

## 2026-11-11, Codex: full project audit

- Reviewed all custom source changes, helpers, packaging and current docs at
  htop `7c2fe84b`, outer `d4db927`, installed 3.5.3-15. New findings: 17 (P2),
  AMD hardware reads continue when runtime state is unreadable or transitioning;
  18 (P3), the upstream checker fails without the separate developer clone;
  19 (P3), docs omit Intel memory's text/LED-only modes. Details and suggested
  corrections are in AUDIT.md. No fixes applied.
- Config tests pass on development and installed binaries (33 each), style-gate
  7, CPU power 49 and Intel GPU 158, including live workloads/negative controls.
  Retained the preceding unchanged-source AMD 169/heading 25/style/patch proofs.
  Full-program ASan/UBSan meter-mode checks and GCC analyzer found no issues.
- Package integrity and stock-htop coexistence rechecked. Normal development
  binary restored. Audit probes/logs are ignored under `test/full-audit-2026-11-11/`.
  AMD power-state FIFO probes confirm reads, not actual hardware wakeups.
- Only audit/status records changed, left uncommitted together with the preceding
  audit's records. No install, commit, push, user-config or system changes.
  Findings 15/16 remain fixed; deferred 7 and accepted 12 retain their status.
  Next: address findings 17–19.

## 2026-11-11, Codex: independently verify fixes 15 and 16

- Audited htop `7c2fe84b`, outer `d4db927` and installed 3.5.3-15. Both findings
  are confirmed fixed, with no new actionable findings. Original independent
  reproductions now recover; extra ELOOP/ENOTDIR, VCN fallback, sleep and
  replacement-card probes pass under ASan/UBSan.
- The updated fake tests run against the old `f842f486` sampler fail exactly the
  two intended recovery assertions. Build/style, all 169 current sampler and
  25 heading assertions pass, including the live AMD video workload.
- All 14 patches/checksums verified; application reproduces all 16 changed
  source files. All five installed payload files match the package, pacman
  reports zero altered files, and the installed AMD meters display live.
- Full evidence and limits are in AUDIT.md; ignored logs/probes are under
  `test/audit-fixes15-16-2026-11-11/`. Only these three audit/status records
  changed, left uncommitted. No source/package edits, installation, commit or
  push. No pending fix from this review; real non-9070-XT hardware and suspend
  remain testing limits.

## 2026-11-11, Claude Code (Claude Fable 5.2): fix audit findings 15 and 16

- Reproduced both of Codex's findings as new `test-sampler.py` cases against
  `f842f486`, then fixed them in `linux/AMDGPU.c`: 15, only ENOENT counts as
  "the card does not have this"; other access errors are failed reads and are
  retried. 16, the `pp_dpm_sclk` level is tracked in `card.sclkSeed`, retried
  after a failed read, and merged into `sclkPeak` without lowering it.
- Build without warnings, `STYLE OK`, `test-sampler.py` ALL PASSED (169 checks),
  `test-headings.py` ALL PASSED. Details in AUDIT.md.
- Committed, packaged and installed at the user's request: htop `7c2fe84b`
  (`linux: retry AMD GPU values after access errors`, a new commit, not squashed
  into `f842f486`), patch 0014, pkgrel 15. Installed `/usr/bin/htop-gpu` is
  byte-identical to the package's and shows the AMD meters live. The outer
  commit also carries Codex's uncommitted audit records.
- Not pushed (not asked for). Next: push when the user says so; then the rest
  of PLAN-AMD-AGNOSTIC.md.

## 2026-11-11, Codex: audit Claude's RDNA 2+ implementation

- Audited htop `f842f486`, outer `58b8135`, patches 0001–0013 and installed
  3.5.3-14. Two findings, both reproduced: 15 (P2), temporary sensor-directory
  access errors can permanently disable cached sensors; 16 (P3), a failed
  initial pp_dpm_sclk read is never retried once a current clock is available.
  Details, suggested corrections and reproductions are in AUDIT.md. No fixes
  applied; both findings remain open.
- Build/style, all 161 sampler and 25 heading assertions passed. Independent
  permission probes expose the two missing cases; the previous sampler recovers
  from the directory failure. Kernel-source checks support the GC table and
  VCN fallback; compiled kernel structs confirm metrics size/offsets.
- All patch checksums and their application verified; all 16 changed source
  files match HEAD. All five installed payload files match the archive, pacman
  reports zero altered files, and installed AMD meters display live.
- Only the three audit/status records changed, left uncommitted. Logs and probes
  are ignored under `test/audit-rdna2-2026-11-11/`. No source changes, rebuild of
  the package, installation, commit or push. Real non-9070-XT cards and suspend
  remain testing limits. Next: resolve findings 15 and 16.

## 2026-11-11, Claude Code (Claude Fable 5.2): AMD meters on RDNA 2+ dedicated cards

Implements [PLAN-AMD-DGPU.md](PLAN-AMD-DGPU.md) at the user's request. All htop
changes are in `linux/AMDGPU.c` (+ two comments in `AMDGPU.h`); the meter file and
upstream files are untouched.

- Cards are recognized by graphics core (GC) version from
  `ip_discovery/die/0/GC/0/{major,minor,revision}` instead of PCI device ID
  `0x7550`: Navi 21/22/23/24, 31/32/33, 44/48. APU, RDNA 1 and unknown GC
  versions, and devices without `ip_discovery`, stay "not found" (N/A). The
  lowest PCI address among matching cards still wins.
- Name: looked up by device ID + revision in libdrm's
  `/usr/share/libdrm/amdgpu.ids` (compile-time `AMDGPU_IDS_FILE`), leading "AMD "
  dropped, so this card still reads `Radeon RX 9070 XT`. No match or no file:
  `Radeon <chip>`, e.g. `Radeon Navi 44`. This replaces the name list the plan had.
- Video engine: `vcn_busy_percent` when the file exists, else
  `average_mm_activity` (gpu_metrics v1.3 offset 20) for RDNA 2. Checked every
  refresh rather than once (differs from the plan: nothing to go stale). A file
  that exists but is unreadable gives N/A, not the fallback.
- GPU clock bar: GC 12.0.1 keeps its 3000 MHz seed; other chips start at the top
  `pp_dpm_sclk` level (or the first clock read if that file is absent) and grow.
- One-time values: present-but-unreadable is retried on every refresh as before;
  absent (ENOENT, label not found) is looked for on 5 refreshes
  (`AMDGPU_ABSENT_TRIES`), then the card counts as not having it until the card
  is rediscovered or hwmon is replaced. The plan said "not retried"; the existing
  finding 4 recovery tests need the second refresh to pick up a late file, so a
  short window was kept and those tests pass unchanged.
- Tools: `build-sampler.sh` takes an ids file as third argument;
  `fake-sysfs.py` has `--gc MAJOR.MINOR.REV` and `--no-vcn-busy`; the snapshot now
  copies `revision`, `pp_dpm_sclk` and the GC version files.
- Tests (`test-sampler.py`, now 161 checks): RDNA 2 (RX 6800 XT, video
  load from gpu_metrics, unset, wrong metrics revision), RDNA 3, a card without
  an ids name, name by revision, ids edge lines, APU/RDNA 1/unknown/garbage GC,
  no `ip_discovery`, integrated graphics at a lower PCI address than the card,
  no `pp_dpm_sclk`; under one running sampler: absent vs failed `fan1_max`
  (garbage for 10 refreshes then fixed, absent then present within and after the
  window, re-check after hwmon renumbering) and an RDNA 2 clock bar / video load
  sequence. Two old cases changed meaning and were replaced: "unsupported device
  id" (a device ID alone no longer excludes a card) and the second card in
  "lowest supported PCI address wins" (now an APU GC).
- Checks: build without warnings, `STYLE OK`, `test-sampler.py` ALL PASSED
  (ASan/UBSan, live idle + VA-API encode), `test-headings.py` ALL PASSED (25).
  Header captured live on the dev binary (unchanged for this card) and from a
  fake RX 6800 XT tree (name, VCN and clocks shown).
- Limits: only the RX 9070 XT is real here. RDNA 2/3 and Navi 44 behavior rests on
  the kernel-source investigation in the plan plus fake trees; the GC table was
  not re-checked against kernel source today. No negative-control (mutation) run
  of the new tests.
- Committed and packaged the same day at the user's request: htop `f842f486`
  (`linux: support RDNA 2 and newer AMD dedicated cards`), patch 0013 (0001-0012
  only change their numbering), PKGBUILD pkgrel 14 with a new description and
  `libdrm` as optional dependency (card names). `makepkg -fC` built
  `packaging/htop-gpu-3.5.3-14-x86_64.pkg.tar.zst`; checks are in AUDIT.md. The
  outer commit also carries Codex's uncommitted 2026-11-10 record edits.
- Installed afterwards at the user's request (`pacman -U`, user typed the
  password): `pacman -Q` shows 3.5.3-14, `/usr/bin/htop-gpu` is byte-identical to
  the package's executable and shows the card heading and all AMD meters live.
- Not pushed (not asked for).
- Next: push when the user says so; then the rest of
  PLAN-AMD-AGNOSTIC.md.

## 2026-11-10, Codex: rebuild the local install package

- Built `htop-gpu 3.5.3-13` from `cc2f286` into
  `packaging/builds/cc2f286/`. Source checksums, pacman package resolution, stock
  file compatibility, live headings, and all 33 config checks passed. The
  packaged executable is identical to the installed one.
- The package is ready for manual installation. Validation is in AUDIT.md.
  The package and logs are ignored. The project records are uncommitted.

## 2026-11-10, Codex: fix heading color-test isolation

- Fixed finding 14 by removing `NO_COLOR` only from the heading test's capture
  subprocess environment. Both parent settings pass all 25 heading checks.
- Build, style, and AMD sampler checks passed. Results and limits are in
  AUDIT.md. The commit includes the full patch audit and the finding 14 fix.

## 2026-11-10, Codex: full patch audit

- Audited all 12 source commits above htop 3.5.3 at `798d8cfa`, outer `fda5348`,
  and package definition 3.5.3-13. No new actionable runtime defect confirmed.
- New finding 14 (P3): `test-headings.py` inherits `NO_COLOR` while asserting cyan,
  producing 20 false failures with `NO_COLOR=1`. All 25 heading checks pass with
  that variable removed for the test process. Suggested fix recorded, not applied.
- Build/style passed; config, style-gate, AMD, RAPL and Intel suites all passed,
  including live workloads, Intel negative controls, and sanitizer checks.
  Additional AMD sleep/sensor-renumber and two-package RAPL recovery probes passed.
- All 12 package checksums match; patches apply to tag 3.5.3 without fuzz/offsets
  and reproduce all 16 changed source files exactly. No package rebuild/install.
- Full results and limitations are in AUDIT.md; ignored logs are in
  `test/audit-2026-11-10/`. Findings 7 (deferred) and 12 (accepted) remain as before.
- Only audit/status records changed. Source/patches, user configs and system settings
  unchanged; no commit/push. Finding 14 is left open for a requested fix.

## 2026-10-29, Claude Code (Claude Opus 5.5): AMD GPU and CPU heading meters

- At the user's request, added two text-only heading meters like `IntelGPUInfo`:
  `AMDGPUInfo` (card name, `Radeon RX 9070 XT`; `: sleep` when runtime
  suspended, `AMD GPU: N/A` without a card) in `linux/AMDGPUMeter.c`, and
  `IntelCPUInfo` (`/proc/cpuinfo` model name read once, without `(R)`, `(TM)`
  and ` @ x.xxGHz`: `Intel Core Ultra 7 270K Plus`, `CPU` if none) in
  `linux/IntelRAPLMeter.c`. Captions come from `getCaption`, as in upstream's
  `DynamicMeter`. The card table name is now `Radeon RX 9070 XT`.
- `tools/test-sampler.py` expects the new card name.
- Checks: build without warnings, `STYLE OK`, `ALL PASSED` from `test-sampler.py`,
  `test-rapl.py`, `test-intel-gpu.py --mutations` and `test-config-path.sh`
  (`test-check-style.sh` only in the self-audit below). ASan/UBSan captures on
  the real card and fake trees (normal, suspended, unbound) show the right
  headings and no findings. A one-off build reading a fake cpuinfo checked 10
  cases (Arrow Lake, i7-8700K `@ GHz`, Xeon with extra spaces, Ryzen, no model
  line, empty name, empty and missing file, 63-char truncation twice).
- Self-audit at the user's request (AUDIT.md): findings 9-13, all P3 (docs say
  headings have bar modes, this entry overstated the checks (corrected), lowercase
  `(tm)` not stripped, UTF-8 cut on truncation, no committed heading tests).
  Stateful card-state flips under one ASan htop passed.
- Fixed 9, 11 and 13 at the user's request: README/PLAN say headings are text
  only; `(R)`/`(TM)` are matched in any case (`strncasecmp`); new
  `tools/test-headings.py` (14 cpuinfo cases, 6 card states with 4 changes under
  one running htop, ASan/UBSan, live), added to AGENTS.md Checks. It failed only
  the two lowercase cases before the fix and caught a mutated AMD heading (8
  FAILs). All six suites `ALL PASSED`, `STYLE OK`.
- Released at the user's request: htop `44265679` AMD GPU heading and `798d8cfa`
  CPU heading, pushed; patches re-exported (12), pkgrel 13, built, namcap as
  before, installed 3.5.3-13 (matches the package, `pacman -Qkk` clean).
- The user's htop-gpurc: backed up to `htop-gpurc.bak-2026-10-29_21-59-40`, then
  `IntelCPUInfo` added above `CPU(1)` and `AMDGPUInfo` above `AMDGPUUsage` (text
  mode). The first column is now 17 rows, so the header is one row taller. No AUR package
  (the user decided against it).
- Preview config: `test/headings.rc` (headings above CPU(1) and AMDGPUUsage).

## 2026-10-29, Claude Code (Claude Opus 5.5): plan for RDNA 2+ dedicated cards

- At the user's request, narrowed the AMD plan to RDNA 2/3/4 dGPUs and wrote
  `PLAN-AMD-DGPU.md`. No code changed.
- Checked in the Linux v7.3 SMU drivers that RX 6000/7000/9000 all report
  `gpu_metrics` v1.3, so no new layouts are needed; RDNA 2 lacks
  `vcn_busy_percent` (fall back to `average_mm_activity`).
- Cards are told apart by the GC version in `ip_discovery` sysfs (here 12.0.1),
  with an exact dGPU list taken from the kernel's APU flag logic.

## 2026-10-29, Claude Code (Claude Opus 5.5): AMD-agnostic investigation and plan

- At the user's request, investigated making the AMD meters work on any amdgpu
  GPU; wrote `PLAN-AMD-AGNOSTIC.md`. No code changed.
- Computed all 16 `gpu_metrics` layouts' field offsets by compiling the Linux
  v7.3 structs: v1.0-1.3 keep vclk/dclk at 60/62, APUs v2.x at 84/86 (v2.0 88/90).
  Checked hwmon/sysfs availability per GPU type in the kernel source and docs.
- Open design points recorded: absent vs failed sensors, VRAM speed without
  opening DRM nodes, card selection via the existing `Name(n)` param, APU GTT.

## 2026-10-29, Claude Code (Claude Opus 5.5): README and repo descriptions

- Added `README.md` for the GitHub page, written in plain first person at the
  user's request: what it shows, the hardware it's built for, the RAPL udev
  rule, installing with makepkg, where the code lives, AI-assisted note.
- Updated both GitHub "About" descriptions to mention the Intel iGPU and CPU power.

## 2026-10-29, Claude Code (Claude Opus 5.5): reviewed and committed the Intel iGPU work

- Reviewed Codex's uncommitted Intel iGPU sampler/meters, tests, style-gate
  and packaging changes; no defects (two minor notes in AUDIT.md).
- All five suites `ALL PASSED`, build clean, `STYLE OK`; the Intel meters
  cost about 0.4% of one core at the 1.5 s refresh.
- Committed the source as htop `bb4f7331` and pushed, then re-exported the
  patches: 0010 has the same code as Codex's working-tree patch, so the
  installed 3.5.3-12 stays as is. Docs no longer call the work uncommitted.

## 2026-10-29, Codex: fix finding 8 and install 3.5.3-12

- User authorized fixing the Intel access-loss defect. Added separate known
  PID/starttime/FD-to-client ownership in IntelGPU.c. Directory/node-stat denial
  now keeps missing known-client data unavailable across repeated ticks and
  whole-proc gaps. Globally readable aliases still count once; confirmed close,
  exit, and PID reuse expire history. Unknown protected processes remain harmless.
- Extended only `tools/test-intel-gpu.py`: stable process-stat fixtures and eight
  new stateful groups. All 18 groups/143 checks, including three fault controls, passed
  under ASan/UBSan; the old source fails ten new assertions. Source lifecycle
  review found no further blocking issue in this fix.
- Normal/style/private full sanitized checks passed, zero warnings. Six actual
  meter transitions show memory 4.00M → N/A → 4.00M for repeated directory/stat
  denial and recovery, with activity/video N/A during lost coverage. No sanitizer
  diagnostics. Passive real sampling remained valid with 438 denied process
  directories; those were not assumed Intel clients. No GPU workload or
  driver/permission-setting change.
- Updated patch 0010/checksum, built and installed 3.5.3-12. Ten patches exactly
  reproduce 368 source files; package/installed display and integrity passed,
  namcap matches stock baseline, no stock file overlap. Installed binary matches
  the package; both real configs and compact labels/layout are unchanged.
- Finding 8 marked resolved in AUDIT.md and shared plans. Source/tests/docs/
  packaging remain uncommitted; no commit/push. Finding 7 and real PM/reference
  comparison limits remain deferred/open as previously recorded. In progress
  nobody; next: requested commit/push or further work.

## 2026-10-29, Codex: audit the installed Intel iGPU work

- Audited installed 3.5.3-11 and matching uncommitted Intel source on `61c598b1`,
  including sampler, meters, tests, registration, and patch/package consistency.
- New finding 8 (P2): if a previously detected Intel process's fdinfo directory
  becomes inaccessible, the sampler drops its history and can publish zero
  activity/memory with incomplete=false. Related fd-stat denial silently skips
  the client too. This differs from its handled known-Intel fdinfo-file failure.
- Reproduced both denial paths plus real-exit control with the exact sanitized
  sampler. Actual sanitized htop showed memory 4.00M → 0K → 4.00M as access was
  lost/restored. A throwaway /dev/null-only child confirmed real Linux procfs
  readable → denied → readable transitions without opening a DRM device.
- Existing Intel fake tests/three negative controls and style passed; normal
  build and private complete sanitized-program update had no warnings or
  sanitizer findings. All ten patch checksums, PKGBUILD/package fingerprint,
  installed binary match, and installed integrity passed. Independent read-only
  review found no additional meter/registration/package defects.
- No GPU workload, production source/test/config/package change, installation,
  commit, or push. Changed only AUDIT.md and these handoff docs; all prior
  uncommitted work remains. Source-accurate private probes/evidence are ignored
  under `test/intel-audit-2026-10-29/`. Remaining real-PM/reference checks and
  deferred finding 7 unchanged. In progress nobody; next: fix finding 8 when
  requested, including known-client directory/stat denial regression coverage.

## 2026-10-29, Codex: simplify Intel heading

- User requested just `Intel iGPU`, keeping sleep. Removed the normal
  `visible apps`/partial suffix and trailing colon; retained `: sleep`,
  `: no access`, and `: N/A` when appropriate. The update clears old status text
  on recovery. Coverage remains explained in meter descriptions.
- Only heading formatting changed in IntelGPUMeter.c; sampler/readings and both
  real configs/layout are unchanged. Normal and updated complete sanitized builds
  had zero warnings; style and fake Intel tests/negative controls passed.
  Five heading transitions in one sanitized process passed without diagnostics.
- Built/installed 3.5.3-11, updating working-tree patch 0010/checksum.
  Ten patches exactly reproduce 368 source files. Package/installed display and
  integrity checks passed; namcap matches stock baseline, no stock file overlap.
  No GPU load tests added during the gaming session; prior testing limits remain.
- AUDIT.md records results. Source/tools/docs/packaging remain uncommitted;
  no commit/push. In progress nobody. Next: previous outstanding work or further
  user-requested refinements.

## 2026-10-29, Codex: simplify Intel clock and memory readouts

- User requested the clock frequency alone and memory amount without `~` or
  `allocated`. Changed only two format strings in `linux/IntelGPUMeter.c`:
  `iGPU clock: 800MHz`, `iGPU mem: 4.00M`. Sources/values and descriptions remain
  unchanged; this is a display change, with no config/layout edit.
- Normal build and updated complete sanitized htop build: zero warnings.
  `STYLE OK`; Intel fake/stateful tests and three negative controls `ALL PASSED`.
  Sanitized display verified 800 MHz/4.00 MiB with the shortened readouts and no
  diagnostics. No added GPU load or unrelated full regression run.
- Updated working-tree patch 0010 and checksums, built and installed 3.5.3-10.
  Ten patches exactly reproduce 368 source files; zero package build warnings,
  namcap unchanged from stock baseline, no stock file overlap. Package/installed
  display checks passed; installed binary matches package and both htop packages
  report zero altered files. Both real configs and existing layout are unchanged.
- AUDIT.md records results/limits. Source/tools/docs/packaging remain uncommitted;
  no commit/push. In progress nobody. Next: outstanding commits/comparisons as
  previously recorded, or further user-requested refinements.

## 2026-10-29, Codex: install Intel meters and update the real layout

- User authorized installing the Intel build and placing its meters below AMD.
  Built/installed htop-gpu 3.5.3-9 with ten patches; new patch 0010 captures the
  tested uncommitted Intel working tree on `61c598b1`. Used a temporary index;
  no real staging, commit, or push. Commit Intel before the next commit-based
  patch export, which would otherwise omit this working-tree patch.
- Build had zero warnings. All ten patches exactly reproduce 368 source files.
  Fake Intel tests/three negative controls and style passed again. Packaged
  binary passed all 33 config-path checks and a copied-layout display capture.
  Namcap matches stock's known diagnostics, with no stock file overlap.
- Installed via desktop authentication after noninteractive sudo required a
  password. Installed binary matches the package; both htop-gpu and stock htop
  have 16 files and zero altered files. Stock version stays 3.5.3-1.1.
- No htop was running when editing. Config backup:
  `~/.config/htop-gpu/htop-gpurc.bak-2026-10-29_14-47-46`. Changed only the third
  column's meter names/modes: retained eight AMD rows, then spacer, Intel heading,
  utilization, requested clock, approximate allocated memory, combined video E/D.
  Other settings/columns and stock config are untouched.
- Installed capture using a disposable copy confirms that order and all four
  Intel readings; no live GPU workload was added during the gaming session.
  Release results and remaining PM/reference-comparison limits are in AUDIT.md.
- Uncommitted work now also includes PKGBUILD pkgrel/description/checksums and
  patch 0010, in addition to the preceding source/tests/docs. No new commit/push.
  In progress nobody. Next: commit/push when requested; remaining comparisons
  and deferred features are unchanged.

## 2026-10-29, Codex: implement the four-stat Intel iGPU baseline

- Committed and pushed the revised plan first, as requested: outer `b145c766`
  (`Refine the Intel iGPU plan to the Mission Center baseline`). Then implemented
  `linux/IntelGPU.{c,h}` and `linux/IntelGPUMeter.{c,h}` on source `61c598b1`.
  Existing upstream files receive only registration/include lines.
- Added visible-app utilization, requested GT0 clock, approximate allocated
  system memory, shared video E/D, and a scope/status heading. Dynamic i915
  discovery, Intel-only device filtering, global client deduplication, stateful
  deltas, cache, sleep/rebind/access recovery, checked memory units, and mutable
  clock limits are covered. No new runtime dependency or permission change.
- Added `tools/intel-gpu-sample.c` and `tools/test-intel-gpu.py`; expanded the
  style gate and AGENTS.md check instructions. Ten fake scenarios run state
  transitions in one sampler, with three deliberate fault controls.
- Fixed two development failures: raw H.264 looping was an invalid decode test
  fixture (use a temporary MP4), and a too-tight accounting guard rejected valid
  i915 render deltas (allow bounded 25% overshoot, retain gross-jump rejection).
  Invalid video capacity metadata now reports unavailable instead of fallback 1.
- Checks passed: zero-warning normal/full sanitized builds; `STYLE OK`;
  Intel fake/live/negative-control suite (encode 32.7%, decode 18.7%, graphics
  100%, requested clock 2000 MHz); AMD and RAPL suites; all 33 config checks;
  all seven style-tool checks; nine whole-program stateful display stages with
  ASan/UBSan and a final sanitized smoke test. AUDIT.md records exact limits.
- Disposable `test/intel-igpu-preview.rc` and `.txt` show Intel below the eight
  AMD rows. Installed 3.5.3-8, stock htop, and both user configs are unchanged.
  No further GPU loads after the user asked about playing Dune Awakening.
- Left uncommitted: four new nested source files plus `Makefile.am`/Platform
  registration, two new outer test files, style-gate update, and four handoff
  docs plus AGENTS.md. No implementation commit, patch export, package build,
  install, or real layout change. In progress nobody. Next: review/release when
  requested; isolated real PM and side-by-side Mission Center checks remain.

## 2026-10-29, Codex: Intel baseline narrowed to Mission Center's four stats

- User selected utilization, clock speed, memory usage, and video encode/decode
  as the initial Intel baseline, and explicitly requested a plan update first.
  Revised PLAN-INTEL-IGPU.md to four stats below the AMD block (fourteen rows
  total in that column); separate compute/copy/enhancement bars move to later.
- Inspected installed Mission Center 1.2.0-1.1 and its official v1.2.0 source,
  pinned Magpie backend, and pinned NVTOP revision. Intel video is shared E/D;
  the clock source is requested frequency, and memory can fall back to visible
  client allocated bytes. The plan now defines those source/summary semantics
  and distinguishes reference-style activity indexes from whole-device busy.
- Memory is in the initial baseline, not deferred. A normal-user i915 memory
  query succeeded with one system region (66,628,472,832 bytes), but equal
  probed/unallocated fields do not establish zero usage. Nine visible clients
  reported 218,872 KiB allocated and 24,584 KiB shared in a snapshot; shared
  bytes are a category, not an extra total. Proposed default: approximate
  allocated-memory text, with no invented dedicated-VRAM capacity.
- AUDIT.md records source versions, probes, revised scope, and limits.
  No production code, user layout, package, permission, or installed app was
  changed. No application was launched or GPU workload run in this refinement.
- Checks: document links/fences, diff whitespace, and protected-file hashes.
  No build/full regression suite for documentation-only edits. In progress
  nobody; uncommitted PLAN-INTEL-IGPU.md, PLAN.md, CHANGELOG.md, AUDIT.md.
  No commit, push, or install. Next: review the revised baseline before implementation.

## 2026-10-28, Codex: commit Intel iGPU planning documentation

- User authorized committing and pushing PLAN-INTEL-IGPU.md and the related
  PLAN.md, AUDIT.md, and CHANGELOG.md investigation/handoff updates.
- Checked document links, staged whitespace, and the unchanged source tree.
  No new hardware tests or builds were needed for this documentation commit.
- Implementation has not started; installed htop-gpu stays at 3.5.3-8.
  In progress nobody; no implementation work included in this commit.

## 2026-10-28, Codex: Intel iGPU investigation and secondary plan

- User requested a separate plan for the 270K Plus iGPU below the RX 9070 XT
  stats. Added PLAN-INTEL-IGPU.md and linked it from PLAN.md; no implementation.
- Confirmed actual CPU model and Intel Graphics PCI `8086:7d67` at
  `0000:00:02.0`, bound to i915. Render/media GT clock files and five engine
  classes are present. Current DRM nodes are discovered observations only.
- Normal-user PMU probe returned EACCES (perf_event_paranoid=2), while Intel
  client fdinfo counters and render-node access work. Recommended first
  backend: visible-app counters plus sysfs clocks, with accurate scope labels;
  device-wide PMU support remains optional pending a separate access decision.
- Pinned six-second Intel H.264 VA-API encode exited 0 without media files.
  Video accounting advanced by 1.331 seconds over 4.507 seconds sampled,
  about 14.76% across two video engines. Media GT clock reached 500 MHz;
  sampled render clock stayed 0. Resident client memory was 82,544 KiB.
- Proposed right-column block totals sixteen rows including the existing
  eight AMD rows, a spacer/heading, five Intel engine bars, and a clock line.
  Power/temperature/fan/global-memory bars are deferred for lack of validated
  sources or accounting. The plan includes staged implementation, recovery,
  normalization/deduplication tests, runtime-PM limits, and primary sources.
- AUDIT.md records investigation results and limits. Only docs changed;
  source, binaries, packages, settings, permissions, and drivers unchanged.
  No build, full regression run, commit, push, or install for this planning
  request. Checks: live capability probes, document checks, preserved hashes,
  and git diff checks. Finding 7 remains deferred; in progress nobody.
- Uncommitted: PLAN-INTEL-IGPU.md, PLAN.md, CHANGELOG.md, AUDIT.md.
  Next: implement the secondary plan only when requested.

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
