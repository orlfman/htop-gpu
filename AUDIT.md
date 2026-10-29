# htop-gpu audit findings

Original audit: 2026-10-28 (America/Phoenix). Latest Intel audit: 2026-10-29.
Auditor: Codex.
Status: findings 1-6 are resolved and validated; finding 6 is committed (`6c06d243`) and retained in installed `htop-gpu 3.5.3-12`, which labels CPU power Pwr. Finding 7 (P3) is deferred at the user's request. Finding 8 (P2, Intel client access loss reported as zero) is fixed and validated in 3.5.3-12; see the fix validation below.
P2 means normal priority; P3 means low priority.

## Scope and baseline

The audit covered the custom sampler and meters, configuration changes, packaging, and project tools.
Read first: `AGENTS.md`, `PLAN.md`, `CHANGELOG.md`, `src/htop/AGENTS.md`, and `src/htop/docs/styleguide.md`.
The project plan listed `In progress: nobody`.

- Outer repository: `92dea33`.
- htop source repository: `7d510f17`, based on upstream tag `3.5.3`.
- Installed package: `htop-gpu 3.5.3-2`, alongside `htop 3.5.3-1.1`.
- Both repositories were clean before and after the audit.

No project or user configuration files were changed during the audit.
Reproduction checks used disposable temporary homes, sampler binaries, and fake sysfs trees, which were removed afterward.
This document is the subsequent, user-requested handoff; it does not authorize implementation, installation, commits, or pushes.
Line numbers below refer to the audited source baseline.

## 1. [P2] Stock config seeding mishandles read-only files and symlinks

Location: `src/htop/Settings.c:1015-1017`.
Related helper: `Settings_read()` at `src/htop/Settings.c:355-377`.

### Observed behavior

With no existing htop-gpu config, three temporary-home cases produced:

| Stock `~/.config/htop/htoprc` | Stock header used | Own `htop-gpurc` saved | Stock contents unchanged |
| --- | --- | --- | --- |
| Regular writable file | Yes | Yes | Yes |
| Read-only file, mode `0400` | Yes | No | Yes |
| Symlink to a readable, writable regular file | No | No | Yes |

Each stock config selected a single `Hostname` text meter so the captured header identified which config was loaded.
The existing development binary was run through `tools/htop-capture.py` with `HTOPRC` and `XDG_CONFIG_HOME` unset and `HOME` pointing to a temporary directory.

### Cause and impact

The fallback calls `Settings_read(this, stockFiles[i], host, this->writeConfig)`.
When `this->writeConfig` is true, the helper checks the stock file using `O_RDWR | O_NOFOLLOW` and updates the same flag that controls saving htop-gpu's own config.
A read-only stock file disables saving to the independent destination.
A symlink causes `ELOOP`, so the helper skips the stock file and also disables saving.
Users with managed or read-only stock dotfiles can lose config persistence or fail to inherit their layout.

### Suggested correction and regression coverage

Read seed files without checking their writability or changing the destination's write decision.
Retain the existing protection for an intentionally read-only htop-gpu config.
Extend `tools/test-config-path.sh` to cover read-only and symlinked stock configs, including legacy `~/.htoprc`, and verify that the source stays unchanged while the independent destination can be saved.

## 2. [P2] GPU and sensor discovery failures persist until restart

Locations: `src/htop/linux/AMDGPU.c:291-293` and `src/htop/linux/AMDGPU.c:321-330`.
Related discovery: `AMDGPU_readStatic()` at `src/htop/linux/AMDGPU.c:265-277`.

### Observed behavior

A temporary sampler built with the existing `tools/build-sampler.sh` reproduced all three cases in fake sysfs trees:

1. Remove the hwmon directory, take a sample, restore the directory, then sample with a newer timestamp.
   Temperatures and clocks remain unavailable even though their files are now present.
2. Take a valid sample, rename the hwmon directory to a different `hwmonN` number, then sample again.
   Initially valid temperatures and clocks become unavailable and do not rediscover the new path.
3. Remove the card's amdgpu driver link, take a sample, restore the link, then sample again.
   Status remains `not_found` after the card becomes bound.

All reproduction processes exited cleanly without ASan or UBSan findings.
No real driver bindings or hardware configuration were changed.

### Cause and impact

`staticRead` becomes true before `AMDGPU_readStatic()` has successfully found the sensor directory and read its metadata.
There is no retry or invalidation for cached hwmon paths.
Separately, card discovery happens only on the first call, and `AMDGPU_NOT_FOUND` prevents later refreshes.
A transient startup failure, later driver binding, or sensor path replacement can therefore leave meters unavailable for the rest of the process lifetime.

### Suggested correction and regression coverage

Retry incomplete discovery and invalidate stale device or hwmon paths when the device disappears or its reads fail.
Preserve the runtime-suspend guard and shared per-tick sample cache when adding retries.
Add sequential recovery tests using one running sampler process; restarting the process for each state hides this issue.

## 3. [P2] Style check can report success when its tools fail

Locations: `tools/check-style.sh:32-38` and `tools/check-style.sh:47-58`.

### Observed behavior

Using exported shell functions only in the audit process, both `include-what-you-use` and `astyle` were replaced with functions that printed an unavailable-tool diagnostic and returned `127`.
The unchanged script still printed `STYLE OK` and exited with status zero.
No tool installations or script files were changed.

### Cause and impact

The script uses `set -uo pipefail`, but does not validate tool availability or handle unexpected tool exit statuses.
The IWYU check relies on selected output patterns; an unexpected failure can match none of them.
If astyle fails, the temporary copy remains identical to the original, so the subsequent diff reports success.
The mandatory style gate can therefore pass without either analysis actually running.

### Suggested correction and regression coverage

Check required tool availability and reject unexpected execution failures.
Handle IWYU's documented exit-status behavior explicitly rather than assuming every nonzero exit has the same meaning.
Verify that absent or failing tools produce a nonzero script exit and no `STYLE OK`, while valid clean files still pass.

## Validation completed

The normal tools and existing suites passed on the audited baseline, but did not cover the issues above:

- `tools/check-style.sh`: `STYLE OK` with the real tools.
- `python3 -I tools/test-sampler.py`: `ALL PASSED`, including ASan/UBSan, fake-tree faults, cache behavior, wake-up, live idle sampling, and VA-API encode load.
  The live video engine reached 100%, with vclk/dclk peaks of 2933/2200 MHz.
- `tools/test-config-path.sh`: all 16 existing checks passed.
- Warning-strict, syntax-only compilation of `linux/AMDGPU.c` and `linux/AMDGPUMeter.c`: passed.
- Python parsing, shell/PKGBUILD syntax checks, and Git whitespace checks: passed.
- All five patch SHA-256 checksums matched `packaging/PKGBUILD`.
- Applying the five patches sequentially to temporary copies of upstream `3.5.3` files reproduced all eight changed development files byte for byte.
- `pacman -Qkk htop-gpu`: 16 total files, zero altered files.
- Final content verification: all 24 regular tracked outer-repository files and all 358 regular tracked htop files matched their respective HEAD commits byte for byte.

A full htop rebuild, package rebuild, reinstall, and new interactive game/VRAM-load checks were not performed during this audit.

## Resolution

Date: 2026-10-28. Fixed by Claude Code (Claude Opus 5.5), at the user's request.
Each finding was first reproduced independently, then covered by a regression test that failed on the audited code, then fixed.
The htop fixes were squashed into the commits they belong to (the user's choice), so `amdgpu-meters` was rebased and force-pushed with lease; the final tree equals the pre-squash tip plus the fixes, and every commit builds on its own with zero warnings.
New hashes: `50714d79` sampler, `75dce070` usage / VRAM / power, `0f0243a9` temperatures and clocks, `e4d2444b` video engine, `8717c760` own config (old: `0c74a6b7`, `4875c09e`, `f45e9ec7`, `fe388c80`, `7d510f17`).
Installed as `htop-gpu 3.5.3-3`.

1. Fixed in `8717c760`: stock config files are read with `checkWritability` off, so read-only and symlinked `htoprc` / `~/.htoprc` are used, left unchanged, and htop-gpu still saves its own `htop-gpurc`.
   A read-only `htop-gpurc` is still never written.
   `tools/test-config-path.sh` grew from 16 to 33 checks; the 17 new ones failed 6 times on the audited build.
2. Fixed in `50714d79`: discovery is retried.
   While no card is found it is looked for on every refresh; a card whose amdgpu driver link disappears is forgotten and looked for again; the one-time reads only count as done once the hwmon directory is found, and are redone when that directory goes away.
   The runtime-suspend guard and the per-tick cache are unchanged (checked by the existing tests).
   `tools/test-sampler.py` has four new recovery cases under one running sampler (all four failed on the audited build).
3. Fixed in `tools/check-style.sh`: it checks that `git`, `include-what-you-use` and `astyle` exist, runs IWYU with `--error=3` (0 clean, 3 findings, anything else a tool failure), and treats a failing astyle as a tool failure.
   Exit codes are now 0 `STYLE OK`, 1 findings, 2 `STYLE CHECK FAILED TO RUN`.
   New `tools/test-check-style.sh` covers clean, each tool failing, both failing, both missing, and a real IWYU and astyle finding (four cases failed on the audited script).

Checks after the fixes: build clean, `STYLE OK`, `test-sampler.py`, `test-config-path.sh` (33) and `test-check-style.sh` all `ALL PASSED`; the config-path suite and a live seven-meter run on the ASan + UBSan htop produced no sanitizer reports; namcap matches stock; the package shares no files with stock htop.


## Independent re-test by Codex

Date: 2026-10-28 (America/Phoenix).
Requested by the user after Claude's fixes.
Result: all three original findings passed re-testing; no failures were found in the checks run.

### Baseline tested

- Outer repository: `6efbb1c0a9f6c5b8c440691de5fdbf0e45247904`.
- htop source repository: `8717c760aea42110b7c2326f186268998df90413`.
- Installed package: `htop-gpu 3.5.3-3`, alongside stock `htop 3.5.3-1.1`.
- Both repositories were clean before and after the re-test.

### Results against the original findings

| Finding | Re-test | Result |
| --- | --- | --- |
| 1. Read-only and symlinked stock configs | `tools/test-config-path.sh`, run once against `src/htop/htop` and once against `/usr/bin/htop-gpu` | All 33 checks passed on each binary. |
| 2. Discovery failed to recover | `python3 -I tools/test-sampler.py` | `ALL PASSED`, including all four recovery cases and no ASan/UBSan reports. |
| 3. Style tools could fail silently | `tools/test-check-style.sh` and `tools/check-style.sh` | All seven regression cases passed; the real style check printed `STYLE OK`. |

Config coverage included read-only and symlinked stock XDG and legacy files, preserving their contents, modes, and links while saving an independent htop-gpu config.
An existing read-only htop-gpu config remained unchanged.
The config suites also covered default paths, precedence, explicit `XDG_CONFIG_HOME`, and `HTOPRC` overrides.

The sampler recovered when hwmon appeared after startup, when hwmon was renumbered, when a card bound after startup, and when a running card was unbound and rebound.
Each recovery case changed state within one running sampler process.
The existing cache, suspended-card, wake-up, malformed/missing-file, and live GPU checks also passed.
Live VA-API encode reached 100% video-engine busy, with vclk/dclk peaks of 2933/2200 MHz.

The style regression suite verified exit 0 for clean files, exit 2 for missing or failing tools, and exit 1 for actual IWYU or astyle findings.
Failing cases did not print `STYLE OK`.

### Additional verification

- Warning-strict, syntax-only compilation of `linux/AMDGPU.c` and `linux/AMDGPUMeter.c`: passed.
- Python parsing, shell/PKGBUILD syntax, and Git whitespace checks: passed.
- All five packaged patch checksums matched `packaging/PKGBUILD`.
- Sequentially applying those patches to temporary upstream `3.5.3` files reproduced all eight changed source files byte for byte.
- Installed stock htop and htop-gpu packages shared no files (shared directories excluded).
- `pacman -Qkk htop-gpu`: 16 total files, zero altered files.
- The installed binary reported `3.5.3-3-gpu`.
- Before/after SHA-256 comparisons verified 390 files unchanged, including tracked project/source files, both tested htop binaries, and the user's stock and htop-gpu configs.

### Scope and limits

The re-test used existing development and installed htop binaries, plus newly compiled temporary sampler binaries with ASan/UBSan.
All temporary test artifacts were outside the project and cleaned up by the test harnesses.
No full htop/package rebuild, reinstall, new whole-htop sanitizer run, or interactive game/VRAM-load check was performed.
No source, package, user config, or project documentation files were changed during the re-test.
This section and the audit status above were updated afterward at the user's request; the re-test did not commit or push anything.


## Fan RPM audit by Codex

Date: 2026-10-28 (America/Phoenix).
Scope: the fan RPM feature and its sampler, display, tests, and packaging changes.
Result: one new P2 finding, open; no fixes applied.
The three earlier findings remain resolved.

### Audited baseline

- Outer repository: `7513b0caf1e320ec26b1316d15a6e2fde49ab8b1`.
- htop source repository: `546413b78d0f298ae895053c1bc60d7f3dc00965` (`linux: add AMD GPU fan meter`).
- Installed package: `htop-gpu 3.5.3-4`, alongside stock `htop 3.5.3-1.1`.
- Read the current agent instructions, plan, changelog, feature diff, upstream rules, and affected tests.
- Both repositories were clean before and after the audit.

### 4. [P2] Failed initial fan maximum read leaves valid RPM stuck at N/A

Locations at this baseline: `src/htop/linux/AMDGPU.c:302-303` and `src/htop/linux/AMDGPUMeter.c:308-311`.

`AMDGPU_readStatic()` returns success after finding hwmon even when reading `fan1_max` fails.
The cached `fanMax` therefore remains NaN, and subsequent refreshes do not retry it while the same hwmon directory exists.
The fan meter requires a valid maximum as well as valid RPM, so it displays `N/A` even when `fan1_input` continues to report a valid speed.
Restoring the maximum file does not recover the display; restarting htop or forcing hwmon rediscovery does.

#### Reproduction

A temporary probe compiled the production sampler and fan meter update/display callbacks with ASan and UBSan.
Only unused UI lifecycle callbacks and an unrelated meter helper were stubbed; the fan sampling and display logic were unchanged.
All file changes below were made in a disposable fake sysfs tree, with one probe process kept running throughout.

1. Keep the hwmon directory present and set `fan1_input` to `1193`, but remove `fan1_max` before the first sample.
2. Sample at timestamp 100: the sampler is active and reads 1193 RPM, but `fanMax` is unavailable and both fan display buffers show `N/A`.
3. Restore `fan1_max` with `3200` and sample at newer timestamps 200 and 300.
   Both still have an unavailable cached maximum and display `N/A`.
4. Rename the hwmon directory to a different `hwmonN` number and sample at timestamp 400.
   Rediscovery reads the maximum and the fan display recovers.

| State | RPM sampled | Maximum sampled | Bar text | Text display, including caption |
| --- | --- | --- | --- | --- |
| First sample, maximum missing | 1193 | unavailable | `N/A` | `Fan:N/A` |
| Maximum restored to 3200; next two samples | 1193 | still unavailable | `N/A` | `Fan:N/A` |
| After hwmon rediscovery | 1193 | 3200 | `1193RPM` | `Fan:1193RPM max:3200RPM` |

The reproduction exited cleanly with no ASan or UBSan findings.
The existing `fan1_max missing` test in `tools/test-sampler.py:276` only checks a fresh process with the file missing; it does not restore the file within that process or check the fan meter's display.

#### Suggested correction and regression coverage

Retry a failed maximum read instead of caching the failure for the entire session.
Preserve the suspended-card guard and shared per-tick cache.
Add a regression test that removes and restores `fan1_max` under one running sampler and verifies that the fan display recovers.
Consider keeping valid RPM visible in text mode when only the maximum is unavailable.

### Checks that passed

- `tools/check-style.sh`: `STYLE OK`.
- `python3 -I tools/test-sampler.py`: `ALL PASSED`, including the new fan cases, existing recovery/cache/suspend cases, live sampling, and VA-API encode under ASan/UBSan.
  Video-engine busy reached 100%, with vclk/dclk peaks of 2933/2200 MHz.
- `tools/test-config-path.sh /usr/bin/htop-gpu`: all 33 checks passed.
- Independent production fan callback probe: spinning (1193 RPM), stopped (0 RPM), missing input, restored input (1800 RPM), garbage input, suspended/awake, and unbound/rebound states all behaved as expected, with no ASan/UBSan reports.
- All four fan modes were exercised live using temporary configs with the installed binary and the existing `test/htop-asan` build.
  Both captures succeeded; the sanitizer build produced no reports.
  Live sysfs reported `fan1_input=0` and `fan1_max=3200`; the displayed stopped state agreed.
- Python parsing, shell/PKGBUILD syntax, warning-strict C syntax, and Git whitespace checks passed.
- All six packaged patch checksums matched `packaging/PKGBUILD`.
- Applying the six patches sequentially to temporary upstream `3.5.3` files reproduced all eight changed source files byte for byte.
- Installed stock htop and htop-gpu shared no files, excluding shared directories.
- `pacman -Qkk htop-gpu`: 16 total files, zero altered files.
- Before/after SHA-256 comparisons verified 395 files unchanged, including tracked project/source files, tested binaries, and both user configs.

### Scope and limits

The physical fan was stopped during live checks; spinning behavior was tested with simulated sysfs readings, not measured on a physically spinning fan.
The audit used existing htop binaries and temporary probe/sampler builds; it did not rebuild or reinstall htop-gpu, change fan controls, or change user configs.
No project files were changed during the audit.
This entry, the audit status, and the related project documentation were updated afterward at the user's request.

### Ongoing audit reporting

User instruction, 2026-10-28: record all future audit and re-test results in this file automatically, including audits with no findings.
The same requirement is recorded in `AGENTS.md` so subsequent agents can follow it.

## Resolution of finding 4

Date: 2026-10-28. Fixed by Claude Code (Claude Opus 5.5), at the user's request.
Reproduced independently first (one running sampler: `fan1_max` missing, then restored, stayed unavailable).
The cause was wider than the fan: every value read once (VRAM total, `pp_dpm_mclk` levels, temperature limits, the temperature and clock labels, `fan1_max`) was cached as missing for the session if its first read failed, because the one-time reads counted as done as soon as hwmon was found.

- Fix: the one-time reads only count as done when all of those values are present (`AMDGPU_staticComplete()`); until then they are tried again on every refresh. The runtime-suspend guard and the shared per-tick cache are unchanged.
  Squashed into the commits it belongs to (the user's choice): the general check into the sampler commit, the `fan1_max` part into the fan commit; `amdgpu-meters` force-pushed with lease.
  New hashes: `6813391d` sampler, `7171bb46` usage / VRAM / power, `0b54b642` temperatures and clocks, `4870d3a8` video engine, `762add8d` own config, `631bc883` fan meter (old `50714d79`, `75dce070`, `0f0243a9`, `e4d2444b`, `8717c760`, `546413b7`).
  The final tree equals the pre-squash tip; each commit builds on its own with zero warnings.
- Regression tests: `tools/test-sampler.py` removes and restores each of `fan1_max`, `mem_info_vram_total`, `pp_dpm_mclk`, `temp2_crit`, `temp3_label`, `freq1_label` and `freq2_label` under one running sampler; all seven failed on the audited code and pass now.
  The fan display was also shown to recover inside one running htop-gpu on a fake card: `Fan:N/A` while `fan1_max` was missing, `Fan:1193RPM max:3200RPM` after it was restored.
- Not adopted: showing the RPM in text mode while only the maximum is missing. VRAM and power already show `N/A` without their totals, and the retry removes the cause.
- Checks: build clean, `STYLE OK`, sampler / config-path / style-check suites `ALL PASSED`, ASan + UBSan htop with all meters and the fan meter produced no reports, namcap matches stock.
  Installed as `htop-gpu 3.5.3-5`.


## Independent re-test of finding 4 by Codex

Date: 2026-10-28 (America/Phoenix).
Requested by the user after Claude's completeness/retry fix.
Result: the fan fix and all seven new recovery cases passed; no new production defect was confirmed.
The full sampler suite failed its first run on one live idle clock reading and passed a single full rerun; both outcomes are retained below.

### Baseline tested

- Outer repository: `cfe216f9dbb4eb9556f61a4aba763edc4c4d9f7b`.
- htop source repository: `631bc883a5c1aad90cd4a31c9d16ecb5447609ec`.
- Installed package: `htop-gpu 3.5.3-5`, alongside stock `htop 3.5.3-1.1`.
- Both repositories were clean before testing; PLAN.md was then marked in progress according to AGENTS.md.

### Finding 4 recovery verified

The seven missing-then-restored cases in `tools/test-sampler.py` all passed on both suite runs:

- `fan1_max`.
- `mem_info_vram_total`.
- `pp_dpm_mclk`.
- `temp2_crit`.
- `temp3_label`.
- `freq1_label`.
- `freq2_label`.

Each case retained one running sampler across the state change and compared the complete sample with the expected values.
The four earlier card/hwmon recovery cases, cache behavior, suspended-card guard, and wake-up cases also passed.
No sampler ASan or UBSan reports were produced.

An independent temporary probe compiled the production sampler and fan update/display callbacks under ASan/UBSan, with only unused UI lifecycle and unrelated meter dependencies stubbed.
It kept one process running through the original failing sequence:

| Step | Maximum | RPM sampled | Bar text | Text display, including caption |
| --- | --- | --- | --- | --- |
| First sample at timestamp 100 | Missing | 1193 | `N/A` | `Fan:N/A` |
| Maximum restored, same or older timestamp | Cached as unavailable | 1193 | `N/A` | `Fan:N/A` |
| Next newer timestamp 200 | 3200 | 1193 | `1193RPM` | `Fan:1193RPM max:3200RPM` |
| Later timestamp 300 | 3200 | 1193 | `1193RPM` | `Fan:1193RPM max:3200RPM` |

The display now recovers without a process restart or hwmon renumbering.
The same/older timestamp checks confirm that the shared per-tick cache is preserved.
The probe exited cleanly with no ASan/UBSan findings.

### Live-clock plausibility observation: follow-up unresolved

The first `python3 -I tools/test-sampler.py` run exited 1 because one live idle sample reported `sclk=0` MHz.
That sample otherwise showed GPU busy 4%, power 30 W, memory clock 456 MHz, temperatures 40/42/42 C, and VRAM about 1.80 GiB.
The other four idle samples, every fake-tree/recovery check, the live encode workload, and sanitizer checks passed.

`tools/test-sampler.py:406-407` requires `0 < sclk <= sclkPeak`, so a zero reading fails the test.
The sampler obtains sclk directly from the labeled hwmon frequency input divided by 1,000,000 (`linux/AMDGPU.c:355` at this baseline).
A follow-up check read the raw labeled sclk file `/sys/bus/pci/devices/0000:04:00.0/hwmon/hwmon8/freq1_input` 60 times over about six seconds.
Those reads ranged from 3,000,000 to 1,276,000,000 Hz and contained no zero values.
A single full rerun of the unmodified sampler suite then exited 0 with `ALL PASSED`; its five idle sclk samples were 43, 37, 51, 50, and 45 MHz.

This establishes that the observed live failure was intermittent, but does not establish why the first zero occurred or whether zero should be accepted by the plausibility check.
No test expectation or production code was changed.
If it recurs, capture the raw sensor read associated with the failing sample before classifying it as a hardware/driver report, a sampling problem, or an overly strict test assumption.
This observation does not reproduce the fixed fan maximum caching issue.

### Other checks completed

- `tools/check-style.sh`: `STYLE OK`.
- `tools/test-check-style.sh`: all seven cases passed, including correct failure exits for unavailable tools and actual style findings.
- `tools/test-config-path.sh`: all 33 checks passed on the development binary.
- `tools/test-config-path.sh /usr/bin/htop-gpu`: all 33 checks passed on the installed binary.
- Live VA-API encode passed on both sampler runs: 100% video busy, vclk/dclk peaks 2933/2200 MHz.
- The existing `test/htop-asan` build exercised all eight meters in all four modes using temporary bar/text and graph/LED layouts; captures succeeded with no sanitizer reports.
  The fan showed `0RPM (stopped)` during the live bar/text check.
- Python parsing, shell/PKGBUILD syntax, and warning-strict C syntax checks passed.
- All six packaged patch checksums matched the PKGBUILD.
- Sequential patch application to temporary upstream `3.5.3` files exactly reproduced all eight changed development source files.
- Installed htop-gpu and stock htop shared no files, excluding directories.
- `pacman -Qkk htop-gpu`: 16 total files, zero altered files; installed version reported `3.5.3-5-gpu`.
- Before writing this report, SHA-256 verification checked 395 files; only PLAN.md differed, due to the deliberate in-progress marker.
  Source files, tested binaries, and both user configs were unchanged.

### Scope, documentation changes, and remaining work

No full htop/package rebuild, reinstall, commit, push, or fan-control change was performed.
The existing sanitizer binary was used for live UI checks; the sampler and independent fan probe were freshly compiled only in temporary directories.
No new physical spinning-fan measurement or game-load run was performed.
The follow-up on the intermittent zero-clock sample remains unresolved; finding 4 itself is independently verified fixed.
This re-test updates only AUDIT.md, PLAN.md, and CHANGELOG.md, and leaves the plan's in-progress marker set to nobody.


## Zero-clock failure investigation by Codex

Date: 2026-10-28 (America/Phoenix).
Requested by the user after the intermittent live-clock failure in the previous re-test.
Baseline: outer HEAD `cfe216f9dbb4eb9556f61a4aba763edc4c4d9f7b`, htop HEAD `631bc883a5c1aad90cd4a31c9d16ecb5447609ec`, installed `htop-gpu 3.5.3-5`.
The uncommitted audit, plan, and changelog updates from the preceding re-test were present and preserved.

### 5. [P2] Idle clock plausibility check rejects a driver-reported zero

Location: `tools/test-sampler.py:406-407` at this baseline.
Status: root cause of the test failure identified; test correction not applied.

The test assumes the GPU clock must be strictly positive for every active-card idle sample.
A traced execution of the unchanged sampler reproduced a successful raw read of `0\n` from the card's labeled sclk sensor.
The sampler converted that value to 0 MHz as written, and the strict-positive assertion rejected it.
This identifies the failing assumption in the live test; the zero was not introduced by parsing or MHz conversion.

### Direct trace evidence

The existing `tools/build-sampler.sh` compiled the current sampler into a temporary binary.
It was run under `strace -qq -ttt -yy -e trace=read -s 128`, with sanitizer leak detection disabled because the process was traced.
ASan/UBSan instrumentation remained enabled.
No source instrumentation, sensor writes, or power-setting changes were used.
The first sampled timestamp, 1 ms, reproduced the zero:

```text
1793233590.559340 read(3</sys/devices/pci0000:00/0000:00:06.0/0000:02:00.0/0000:03:00.0/0000:04:00.0/hwmon/hwmon8/freq1_input>, "0\n", 31) = 2
```

The corresponding sampler output included:

```json
{"status":"active","gpuBusy":4,"sclk":0,"sclkPeak":3000,"mclk":456,"power":32,"temp":[40,41,42],"fan":0,"fanMax":3200}
```

The read returned two bytes successfully, rather than an I/O error or an empty file.
The sampler exited 0 with empty stderr and no ASan/UBSan findings.
The path above is the resolved sysfs path reported by strace; production discovery still uses the PCI address and labels rather than hardcoded card/hwmon numbers.

### Driver path and why idle readings differ

The running kernel is `7.3.0-4-cachyos`.
Read-only GPU IP discovery reported MP1 `14.0.3` and GC `12.0.1`.
The matching versioned upstream Linux v7.3 code was inspected, with the following relevant path:

1. [SMU selection in amdgpu_smu.c](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/pm/swsmu/amdgpu_smu.c#L786-L789) maps MP1 14.0.3 to `smu_v14_0_2_set_ppt_funcs()`.
2. [amdgpu_hwmon_show_sclk()](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/pm/amdgpu_pm.c#L3499-L3513) reads `AMDGPU_PP_SENSOR_GFX_SCLK` and emits its value in Hz; sensor errors return an error instead of being converted to a successful zero read.
3. [smu_v14_0_2_read_sensor()](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/pm/swsmu/smu14/smu_v14_0_2_ppt.c#L864-L870) obtains that clock from `METRICS_AVERAGE_GFXCLK`.
4. [The average-clock selection](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/pm/swsmu/smu14/smu_v14_0_2_ppt.c#L661-L666) uses `AverageGfxclkFrequencyPostDs` when `AverageGfxActivity <= 5`, and `AverageGfxclkFrequencyPreDs` above that threshold.
5. The project's `linux/AMDGPU.c:355` reads the labeled hwmon value and divides by 1,000,000; there is no positive minimum or substitution in that conversion.
6. `tools/test-sampler.py:406-407` then rejects 0 because it requires `0 < sclk <= sclkPeak`.

The successful zero read is proven on the installed driver by the trace.
The versioned upstream source explains that the selected sensor is a firmware-backed average with a separate low-utilization path; the reproduced sample reported 4% GPU busy.
[Kernel GFXOFF documentation](https://docs.kernel.org/gpu/amdgpu/thermal.html#gfxoff) also explains that supported GPUs can power down their graphics engine dynamically at idle.
The precise firmware/GFXOFF state at the instant of the trace was not recorded, so attributing that individual zero specifically to a GFXOFF transition remains an inference, not a measured fact.
The investigation did not compare every CachyOS kernel patch with upstream.

### Additional cross-check and its limits

A separate read-only probe made 60 paired reads of the raw sclk sensor and `gpu_metrics` about 0.3 seconds apart.
It did not capture another zero from the raw sclk file.
Its first pair showed raw hwmon 60 MHz while `gpu_metrics` reported average/current gfxclk 0 MHz, gfx activity 0%, and runtime status `active`.
Those reads are separate snapshots, so their difference is not evidence of a unit conversion error.

The [v7.3 gpu_metrics exporter](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/pm/swsmu/smu14/smu_v14_0_2_ppt.c#L2216) also assigns `current_gfxclk` from `average_gfxclk_frequency` on this path.
Consequently those two gpu_metrics fields are not independent instantaneous-clock checks.
The earlier 60 raw reads and later full passing suite remain valid historical results; they simply did not land on the zero sample captured here.

### Recommended correction and regression coverage

Allow a nonnegative clock in the idle plausibility check (`0 <= sclk <= sclkPeak`), retaining rejection of missing values, negative values, invalid identity/status, and an invalid peak seed.
Keep positive-clock checks tied to an actual graphics workload if such validation is added; video-engine activity alone should not be treated as proof of a continuously busy graphics clock.
Add a fake-sysfs case with `freq1_input=0` to preserve the expected sampler result and guard against treating reported zero as missing or corrupt.
Do not change the sampler's units, force a positive fallback, or change GPU power settings to make the idle assertion pass.
No correction was applied during this diagnostic request.

### Preservation and handoff

The trace and downloaded source excerpts were held in temporary files or memory; the key evidence and source links are preserved in this audit entry.
Before the report update, 394 file hashes were checked and only PLAN.md's deliberate in-progress marker differed from the investigation baseline.
Production source, tested binaries, and both user configs stayed unchanged.
Only AUDIT.md, PLAN.md, and CHANGELOG.md were updated for this investigation; no rebuild of htop-gpu, install, commit, or push was performed.


## Resolution of finding 5

Date: 2026-10-28 (America/Phoenix).
Fixed by Codex at the user's request.
Status: resolved and validated; changes remain uncommitted.

### Change

Only the test harness needed correction; production sampler/meter code and installed package `3.5.3-5` remain unchanged.
`tools/test-sampler.py` now shares `valid_idle_sclk()` between the live plausibility check and the regression coverage.
It accepts `0 <= sclk <= sclkPeak` while requiring a present clock, a present peak, and a peak at least equal to the card's 3000 MHz seed.
Missing, negative, and above-peak readings remain invalid; missing and below-seed peaks are also rejected.
Identity, status, memory-clock, power, temperature, fan, and video checks are unchanged.

The fake-sysfs regression changes `freq1_input` from 0 Hz to 1,500,000,000 Hz and back to 0 Hz under one running sampler.
At each newer timestamp it checks the complete sample against the independently computed expected values and exercises the same idle-clock validator used by the live test.
This covers zero as a reported value and the transition back from a positive reading without restarting the sampler.
Five additional guard cases verify rejection of missing clocks, negative clocks, clocks above the peak, missing peaks, and peaks below the seed.

### Validation

- `python3 -I tools/test-sampler.py`: exit 0, `ALL PASSED`.
  The zero -> positive -> zero regression, all five invalid-reading guard cases, the prior fault/cache/suspend cases, all eleven existing recovery cases, live idle sampling, and live VA-API encode passed under ASan/UBSan.
  No sanitizer findings were produced; video busy reached 100%, with vclk/dclk peaks of 2933/2200 MHz.
- A focused check of the shared validator passed all seven zero/positive/invalid acceptance and rejection cases.
  An in-memory negative control restoring the old strict-positive comparison rejected zero while still accepting 1500 MHz, confirming that the regression distinguishes the old boundary from the corrected one.
- `tools/check-style.sh`: exit 0, `STYLE OK`.
- Full `make` validation in a disposable copy of the configured htop tree, with object files and binaries excluded from the copy: exit 0, zero warnings.
  The existing development and installed binaries were not rebuilt or replaced.
- Python syntax parsing and `git diff --check`: passed.
- Final hash verification confirmed that all protected tracked source files, the existing development/installed htop binaries, and both user configs remained unchanged.

### Handoff and limits

The source repository remains at `631bc883a5c1aad90cd4a31c9d16ecb5447609ec`; the outer HEAD remains `cfe216f9dbb4eb9556f61a4aba763edc4c4d9f7b` with local changes.
Uncommitted files: `tools/test-sampler.py`, `AUDIT.md`, `PLAN.md`, and `CHANGELOG.md`.
The preceding audit and trace documentation was preserved.
No package rebuild, reinstall, power-setting change, commit, or push was performed.
No new findings were identified by this scoped fix validation.


## Intel CPU power audit — 2026-10-28

Auditor: Codex.
Original audit status: two new findings, 6 (P2) and 7 (P3), with no fixes applied during that audit.
Finding 6 is subsequently fixed and validated below; finding 7 is deferred at the user's request.
Findings 1-5 remain resolved.

### Scope and baseline

Reviewed the new Intel RAPL sampler, CPU meter, Linux registration, test driver,
test suite, packaging patch, and current project documentation.
Read `AGENTS.md`, `PLAN.md`, `CHANGELOG.md`, `src/htop/AGENTS.md`, and
`src/htop/docs/styleguide.md` before testing.
Both repositories were clean and the plan listed nobody in progress.

- Outer repository: `4c631711c6835a79b890853def36292bf949564e`.
- htop source repository: `363370bdb3e87ca966224dfb08a3b5a56eaf29f8`, based on upstream `3.5.3`.
- Installed: `htop-gpu 3.5.3-6`, alongside `htop 3.5.3-1.1`.
- Live hardware: one readable package, `/sys/class/powercap/intel-rapl:0`, named `package-0`.
- Line references below refer to this htop source revision.

### 6. [P2] CPU power limit stays stale after PL1 changes

Locations: `src/htop/linux/IntelRAPL.c:127-155` and `166-167`.
Display impact: `src/htop/linux/IntelRAPLMeter.c:37-39` and `50-55`.

The sampler treats the long-term power limit as immutable.
Once `IntelRAPL_readLimits()` succeeds, `limitsRead` remains true and the
sampler stops reading `constraint_N_power_limit_uw` until the zones are forgotten.
However, Linux documents `constraint_X_power_limit_uw` as a writable setting,
so a legitimate power-limit change during an htop session leaves the displayed
limit and bar/graph scaling based on the old setting.
See the [Linux powercap constraint documentation](https://cdn.kernel.org/doc/html/latest/power/powercap/powercap.html#constraints).

Reproduced with the unchanged production sampler under one process and a
temporary fake sysfs tree; no real CPU settings were changed:

| Timestamp (ms) | Package energy (uJ) | PL1 file (uW) | Actual sampler result | Expected limit |
| --- | --- | --- | --- | --- |
| 100 | 1,000,000 | 250,000,000 | first sample, limit 250 W | 250 W |
| 1100 | 62,000,000 | 250,000,000 | 61 W, limit 250 W | 250 W |
| 2100 | 123,000,000 | 65,000,000 | 61 W, limit **250 W** | **65 W** |

An independent probe compiled the production sampler and meter together and
called the actual meter update/display callbacks through the same sequence.
The final bar text stayed `61.0W/250W`, its total stayed 250, and the text display
stayed `:61.0W limit:250W` after the limit file became 65 W.
The measured wattage was correct; the denominator, displayed limit, and chart
normalization were stale.
Both probes exited cleanly under ASan/UBSan.

Suggested correction: refresh the mutable PL1 value on newer sampler ticks,
while retaining shared same/older-timestamp caching and any appropriate cache
for genuinely static counter metadata.
Add a regression that changes a valid limit to another valid limit in one
running process, checks the new sample and actual meter text/total, and verifies
that a repeated timestamp still returns the cached result.
Also cover a limit becoming unavailable and recovering so stale values do not
silently survive a failed refresh.
The existing test only covers a limit missing initially and appearing later;
it does not change a limit after its first successful read.

### 7. [P3] Partial discovery prevents later CPU packages from being counted

Location: `src/htop/linux/IntelRAPL.c:158-164`.
Related enumeration: `src/htop/linux/IntelRAPL.c:95-125`.

Discovery runs only while `zoneCount` is zero.
If one package is discovered successfully, another package appearing later is
never added while the first package remains readable.
This affects multi-package systems with delayed package-zone registration or
package hotplug, and does not affect the currently observed single-package host.

Reproduced using the unchanged production sampler and temporary fake sysfs,
keeping one process alive throughout:

1. At 100 ms, create only `intel-rapl:0`, named `package-0`, with energy
   1,000,000 uJ and PL1 250,000,000 uW; sample reports one package.
2. At 1100 ms, set package 0 energy to 11,000,000 uJ; sample reports 10 W/250 W.
3. Before 2100 ms, create `intel-rapl:1`, named `package-1`, with energy
   1,000,000 uJ and PL1 125,000,000 uW; advance package 0 to 21,000,000 uJ.
   The sample still reports only one package.
4. At 3100 ms, set package 0 energy to 31,000,000 uJ and package 1 energy to
   21,000,000 uJ. A sampler that discovered and baselined the new package at
   2100 ms would now report **two packages, 30 W, limit 375 W**.
   Actual result remains **one package, 10 W, limit 250 W**.

The process exited cleanly under ASan/UBSan.
Suggested correction: periodically reconcile the discovered package set,
preserving previous energy values for unchanged packages and baselining newly
found ones before calculating their power.
Add a same-process one-package -> two-package test, followed by another
refresh to check the combined energy delta and power limits.
The existing two-package test starts with both present, and the appearance
test starts with no packages; neither exercises partial discovery.

### Validation completed

- `python3 -I tools/test-rapl.py`: `ALL PASSED`, exit 0.
  Existing delta, wrap, same/older tick cache, multi-package sum, unreadable
  counter recovery, discovery/reappearance, delayed limit, and garbage cases
  passed with ASan/UBSan.
  Live pre-load power was 21.722 W and busy power was 128.059 W.
  Other audit suites ran concurrently, so the pre-load reading is a
  plausibility check rather than a controlled idle benchmark.
- Independent live comparison: bracketed each sampler read with raw
  `energy_uj` reads and calculated delta bounds using the supplied timestamps.
  Reported power fell inside both bounds: 12.265 <= 12.283 <= 12.393 W,
  then 9.854 <= 9.870 <= 9.888 W.
  Clean ASan/UBSan exit.
- Independent production-meter checks passed for permission denied -> readable
  -> valid watts, malformed energy -> rediscovery/baseline -> valid watts, and
  a missing counter range restored during the same process.
  Expected `no access`, `N/A`, and restored watt text were verified through
  the actual update/display callbacks; ASan/UBSan clean.
- `python3 -I tools/test-sampler.py`: `ALL PASSED`, exit 0.
  Includes the earlier zero-clock regression, discovery/metadata recovery,
  fake fault/cache/suspend cases, live plausibility, and live VA-API encode.
  An actual live GPU sample had sclk 0 MHz and passed the corrected validator.
  Video busy peaked at 100%, vclk/dclk at 2933/2200 MHz; ASan/UBSan clean.
- `tools/test-config-path.sh`: `ALL PASSED`, exit 0, using disposable homes.
- `tools/test-check-style.sh`: all seven cases passed, exit 0.
- `tools/check-style.sh`: `STYLE OK`, exit 0, including the new production RAPL files.
- Full normal build and full ASan/UBSan build in a disposable copy: both
  passed with zero warnings. Existing development/installed binaries were
  not rebuilt or replaced.
- A fresh sanitized full htop ran the CPU meter in bar, text, graph, and LED
  modes simultaneously with a disposable config. Captured real watts and
  the 250 W limit; no sanitizer log files or error output were produced.
  This was a terminal capture smoke test, not an interactive F2 setup test
  or an independent pixel-by-pixel verification of graph/LED rendering.
- All seven package patch SHA-256 checks passed. Applying all seven to the
  local upstream `3.5.3` archive exactly reproduced all 364 tracked htop files.
- `pacman -Qkk htop-gpu htop`: exit 0, both packages have 16 files and zero
  altered files.
- Python syntax parsing and `git diff --check` passed.

### Preservation, limits, and handoff

Before the report update, fingerprints of 402 tracked/protected files were
checked; only the deliberate PLAN.md in-progress marker differed.
The protected set included both repositories' tracked files, existing normal
and sanitizer htop binaries, installed htop/htop-gpu binaries, and both user configs.
No real sysfs settings, udev rules, packages, or user configs were changed.
Only AUDIT.md, PLAN.md, and CHANGELOG.md were modified for this audit.
No install, commit, or push was performed; the plan is back to nobody in progress.

Real hardware testing covered the current readable single Intel package and
the RX 9070 XT; permission faults, counter wrap, recovery, limit changes, and
additional packages were simulated in temporary trees.
No physical package hotplug, actual PL1 write, suspend/resume cycle, or
comparison against external electrical power measurement was performed.
The packaged patches were verified, but no new package was built or installed.
The existing suites pass because they do not cover the two runtime transitions
above. Permanent regression tests and implementation fixes remain to be done
if requested.


## Resolution of finding 6 — mutable Intel PL1

Date: 2026-10-28 (America/Phoenix).
Fixed by Codex at the user's request.
Status: resolved and validated in local source; uncommitted, not installed.
Finding 7 remains deferred at the user's explicit request; its discovery logic
was not changed.

### Change and version

Baseline: outer `4c631711c6835a79b890853def36292bf949564e`, htop
`363370bdb3e87ca966224dfb08a3b5a56eaf29f8`, plus the local changes described here.
The preceding audit documentation was already uncommitted and was preserved.

`src/htop/linux/IntelRAPL.c` no longer caches the long-term power limit forever.
`IntelRAPL_readLimits()` now runs on each newer sampler tick and rereads PL1
for each already discovered package.
It clears the previous limit before reading, so a missing, unreadable, or
unparsable limit becomes unavailable instead of silently retaining the old value.
The static energy-counter range is cached once read successfully, and retried
while unavailable.
The shared same/older-timestamp cache, energy-delta calculation, wrap handling,
permission status, and package discovery behavior remain intact.

No meter code change was necessary: its existing update/display callbacks use
the refreshed sample limit for text and chart total, and show N/A while the
limit is unavailable.

### Regression coverage and validation

- Added a single-process scenario to `tools/test-rapl.py` that changes a valid
  PL1 from 250 to 65 W, removes and restores it as 125 W, supplies malformed
  data, denies read permission, and restores a valid readable limit.
  Throughout, the energy steps independently imply 61 W.
  The scenario checks fresh limits on newer ticks and cached limits on
  same/older ticks, including an unavailable limit restored during a cached tick.
- Added a counter-range recovery case: start with the range missing and the
  energy near wrap; restore the range on the next tick and verify a 3 W
  wrapped delta. This guards the separate static-range retry behavior.
- **Before the fix:** the updated CPU suite exited 1 with seven new limit
  assertions failing because the sample kept its old 250 W limit.
  The existing tests and new range-recovery test passed; ASan/UBSan clean.
- **After the fix:** `python3 -I tools/test-rapl.py` exited 0, `ALL PASSED`,
  including both new scenarios and all previous tests under ASan/UBSan.
  Live pre-load power was 12.397 W and busy power 127.431 W; these are
  plausibility checks, not controlled power benchmarks.
- An independent temporary probe compiled the production sampler and meter
  together under ASan/UBSan and called the actual update/display callbacks
  through the changing-limit sequence without restarting.
  The changed limit produced bar text `61.0W/65W`, text `:61.0W limit:65W`,
  and chart total 65. Restoring 125 W updated all three accordingly.
  Missing, malformed, and unreadable limits produced `N/A`/`:N/A`, and valid
  reads recovered. Same/older ticks preserved the cached display.
  All checks passed with a clean sanitizer exit.
- `python3 -I tools/test-sampler.py`: exit 0, `ALL PASSED`, including existing
  fault/recovery/cache coverage, live idle sampling, and VA-API encode.
  Video busy peaked at 100%, vclk/dclk at 2933/2200 MHz; ASan/UBSan clean.
- `tools/check-style.sh`: exit 0, `STYLE OK`.
- Full normal build and full ASan/UBSan build in a disposable copy of the
  current configured source: both passed, zero warnings.
- The fresh sanitized full htop ran the CPU meter in bar, text, graph, and
  LED modes together with a disposable config. Captured 15.8 W/250 W;
  no sanitizer files or error output were produced.
  This was a terminal capture smoke test rather than an interactive F2 test
  or a pixel-level verification of graph/LED output.
- Python syntax parsing and `git diff --check` passed.

### Preservation and handoff

Before the report update, fingerprints of 402 files were checked.
Only the intended `linux/IntelRAPL.c`, `tools/test-rapl.py`, and PLAN.md work
marker differed from this fix session's baseline.
The baseline included the prior uncommitted audit/handoff docs.
Existing development/sanitizer binaries, installed binaries, both user configs,
and all packaging files remained unchanged.
Limit changes, read faults, and range recovery were simulated in temporary
sysfs trees; no real CPU limits or udev rules were changed.

Uncommitted files: outer `AUDIT.md`, `PLAN.md`, `CHANGELOG.md`, and
`tools/test-rapl.py`; nested `linux/IntelRAPL.c`.
No install, commit, or push was performed.
Installed `htop-gpu 3.5.3-6` and packaging patch 0007 still have the previous
code: the source fix must be committed and exported before a future package
contains it. No package rebuild was performed.
Finding 7 was intentionally not addressed, and no new findings were identified
by this scoped fix validation.


## Finding 6: review, commit and install

Date: 2026-10-28. Claude Code (Claude Opus 5.5), at the user's request ("review, commit, push, and install if it's all good").

- Reviewed Codex's change to `linux/IntelRAPL.c` and the new `tools/test-rapl.py` scenarios: the limit is read on every newer tick, cleared before each read so a failed read cannot keep an old value, the static counter range is cached once read, and the shared per-tick cache is unchanged. Agreed with the fix.
- Re-ran independently: build clean, `STYLE OK`, `test-rapl.py` `ALL PASSED` (live 9.2 W idle, 126.3 W busy); against the previous `IntelRAPL.c`, the suite fails 7 of the new limit checks, so they catch the stale limit.
- Committed as a new commit on `amdgpu-meters`, `6c06d243` (`linux: read the Intel CPU power limit on every refresh`), crediting Codex. Folding it into `363370bd` would have needed a force-push, which was not part of this request, so history was left as is.
- Packaged as `htop-gpu 3.5.3-7` (8 patches), namcap as stock, config-path checks pass on the packaged binary; installed.
- Finding 7 stays deferred.


## CPU caption Pwr: release validation

Date: 2026-10-28 (America/Phoenix). Codex.
Scope: the user authorized renaming the CPU power caption from CPU to Pwr,
committing, pushing, packaging, and installing the result.
No new findings; finding 7 remains deferred at the user's request.

### Baseline and change

- Outer baseline: `d6b2a3d7d47e45b4e5452db6d49063114153c6b5`.
- Source baseline: `6c06d243`; installed package before release: 3.5.3-7.
- Both repositories were clean and PLAN.md listed nobody working.
- Re-read shared docs and upstream coding instructions/style guide, including
  Claude's finding 6 commit/install handoff.
- Source revision: `61c598b1a128e06864a4f071347d6ed63ce71282`,
  `linux: label Intel CPU power meter Pwr`, committed and pushed to
  `origin/amdgpu-meters` without rewriting history.
- The sole source change is `.caption = "Pwr"` in `linux/IntelRAPLMeter.c`.
  Internal name `IntelCPUPower` and the separate `AMDGPUPower` meter remain
  unchanged; no configuration migration is necessary.

### Validation

- Normal build: passed, zero warnings.
- `tools/check-style.sh`: exit 0, `STYLE OK`.
- `python3 -I tools/test-rapl.py`: exit 0, `ALL PASSED`, including the
  stateful changing-limit/failure/recovery regression from finding 6.
  Live CPU pre-load/busy values were 10.363/127.654 W; ASan/UBSan clean.
- `python3 -I tools/test-sampler.py`: exit 0, `ALL PASSED`.
  Live VA-API encode reached 100% video busy and 2933/2200 MHz video clocks;
  ASan/UBSan clean.
- `tools/build-htop-asan.sh` completed its full sanitized build and normal
  restore with zero warnings. A temporary four-column config placed CPU
  and GPU power together in bar, text, graph, and LED modes.
  Both rendered Pwr captions; CPU text used `limit:` and GPU text used `cap:`.
  No sanitizer reports or error output; both internal names survived config save.
- Exported all nine patches with `tools/export-patches.sh`; each SHA-256
  check passed. Applying the series to upstream tag 3.5.3 exactly reproduced
  all 364 tracked htop files. The first eight patches only changed their
  generated series numbering from /8 to /9.
- `makepkg -fC --noconfirm`: built `htop-gpu 3.5.3-8`, zero compiler warnings.
  Extracted package reports `htop 3.5.3-8-gpu` and shows separate CPU/GPU Pwr
  captions with valid watt readings.
- `tools/test-config-path.sh <extracted package binary>`: exit 0,
  all 33 checks passed using disposable homes.
- No packaged file paths overlap stock htop's files.
  Namcap matches the stock baseline: missing hicolor-icon-theme dependency,
  implicitly satisfied glibc, and possibly unneeded libnl. Stock additionally
  reports its existing GPL license-format issue; the custom package does not.

### Installation and preservation

Installed `packaging/htop-gpu-3.5.3-8-x86_64.pkg.tar.zst` through the system's
authentication dialog after noninteractive sudo required a password.
The package manager completed the upgrade from 3.5.3-7 to 3.5.3-8 successfully.

- Installed version: `htop 3.5.3-8-gpu`.
- Installed binary SHA-256 matches the binary extracted from the built package.
- `pacman -Qkk htop-gpu htop`: both have 16 total files and zero altered files.
- Ran the installed binary with a disposable copy of the user's actual layout;
  both CPU and GPU Pwr bars appeared (12.3 W/250 W and 37 W/304 W in that capture).
- Stock htop remains 3.5.3-1.1. All seven protected stock-file/user-config
  hashes match the pre-release baseline; the real configs were not edited.

This was a caption/package validation, with terminal capture smoke tests rather
than interactive F2 or pixel-level graph/LED testing.
No new hardware support or package-discovery changes were introduced.
PLAN.md and CHANGELOG.md record the release, and in progress is back to nobody.


## Intel iGPU feasibility investigation

Date: 2026-10-28 (America/Phoenix). Codex.
Scope: investigate this machine and write a secondary plan for Intel stats
below the existing RX 9070 XT meters; implementation was not requested.
Plan: [PLAN-INTEL-IGPU.md](PLAN-INTEL-IGPU.md).
No new production defect findings; finding 7 remains deferred.

### Baseline and observations

- Outer `8601dca3e9715af70a099d40b1a707ea63766e93`, htop source
  `61c598b1a128e06864a4f071347d6ed63ce71282`; both initially clean.
  Installed htop-gpu 3.5.3-8; shared plan listed nobody working.
- CPU confirmed as Intel Core Ultra 7 270K Plus. Intel Graphics is PCI
  `8086:7d67`, revision 06, at `0000:00:02.0`, bound to i915.
  Current nodes card1/renderD128 map to it; AMD is card2/renderD129 at
  `0000:04:00.0`. Stable by-path names are available to pin workloads.
- Per-GT actual/requested/limit clock files exist. GT0 maximum is 2000 MHz,
  GT1 maximum 1400 MHz. Idle samples can report 0 MHz with runtime active.
- Readable Intel client fdinfo includes render, compute, copy, video, and
  video-enhance busy-time counters. Video engine capacity is two.
  Ten distinct clients were found in one inventory after identity deduplication.
  Inaccessible/raced process directories mean access is incomplete; their
  count is not a count of hidden GPU clients.
- i915 PMU events exist, but an actual normal-user perf_event_open attempt
  for rcs0-busy failed with EACCES (13). perf_event_paranoid is 2; DRM nodes
  themselves are readable/writable by this user. No permissions were changed.
- No Intel device hwmon directory was found. RAPL package energy is readable,
  but core/uncore energy is not, and uncore was not verified as isolated iGPU
  power on this platform. No usable iGPU temperature/direct-power source
  was established. Client memory counters are not a unique global VRAM total.

### Live validation

A six-second 1080p60 H.264 VA-API encode was explicitly pinned to
`/dev/dri/by-path/pci-0000:00:02.0-render`, with output discarded through the
null muxer. It exited 0, with no error output and no generated video file.

Ten snapshots showed one Intel client and 82,544 KiB resident system memory.
From the first to last sampled interval, video busy time increased by
1,330,747,548 ns over approximately 4.507 seconds.
Using the reported capacity of two gives about 14.76% combined video capacity
usage over those sampled intervals, not a render or whole-device percentage.
Media GT1 actual clock was observed at 500 MHz; GT0 was 0 MHz in the snapshots.
This validates live video accounting but does not test render/compute/copy/
enhancement workloads or video decode.

Runtime state was observed both suspended and active at different times.
Activity outside the explicit workload was not isolated, so this investigation
does not prove a passive future sampler will preserve runtime suspend.
That is an explicit implementation acceptance test in the secondary plan.

### Design conclusion and preservation

The secondary plan starts with normal-user, visible-client engine activity
and separate render/media clocks. It proposes a sixteen-row right column,
retaining the eight AMD rows above the Intel block.
Optional PMU access, global memory accounting, and power/temperature sensors
remain separate work, with no fabricated readings or device-wide claims.
Primary Linux ABI/driver/perf references are linked in the plan.

Before writing the plan/report, all 403 baseline file fingerprints matched,
including both repositories' tracked files, existing binaries, and both user
configs. The baseline was captured after the temporary PLAN.md work marker.
Only PLAN-INTEL-IGPU.md, PLAN.md, CHANGELOG.md, and AUDIT.md were edited.
No production source, installed package, user config, sysctl, udev rule,
capability, or driver binding was changed.
Temporary probe code and downloaded primary source excerpts were used only
for investigation. No project build/full regression suite was run for these
documentation-only changes; validation was the hardware probes, document
checks, fingerprint preservation, and git diff checks.
The plan and handoff docs remain uncommitted; no push or install was performed
for this request. In progress is back to nobody.

Commit follow-up: the user subsequently authorized committing and pushing
the secondary plan and its audit/handoff documentation.
Those four documents are included in the planning commit; no implementation,
package, settings, or additional hardware-test changes are included.


## Intel baseline refined against Mission Center

Date: 2026-10-29 (America/Phoenix). Codex.
User selected utilization, clock speed, memory usage, and video encode/decode
as the first Intel iGPU baseline, then explicitly requested a plan update
before implementation. No new production defect finding; finding 7 stays deferred.

### Source and package versions inspected

- Project baseline: outer `51c64de5305ece34a6d67c3fcced9c1d78bf4e11`, source
  `61c598b1a128e06864a4f071347d6ed63ce71282`; both initially clean.
- Installed Mission Center: `1.2.0-1.1`. Its binaries have no file capabilities
  in this installation. The application/backend were not launched for this work.
- Official Mission Center `v1.2.0`: `193e3729367035cf184da004c3246efe79d5c53e`.
  Pinned Magpie: `a5272b3c1d853caa4044b737cf49257bfc4c86f2`.
  Pinned NVTOP: `3d4a953da02bc18886734613bb9f60ff80669de7`.
  Primary source links and relevant semantics are in PLAN-INTEL-IGPU.md.

The reference's Intel path marks video encode/decode shared and takes both
internal video rates from the same counter. The UI presents the shared case
as video encode/decode. It uses requested frequency for the clock reading,
and can estimate memory from per-client allocated bytes rather than resident
bytes when direct used/free data is unavailable.
Its utilization summary is a visible-client render/compute work proxy,
and display saturation does not make it a whole-device busy-time measurement.
The revised plan specifies these distinctions and an explicit video denominator
convention, rather than copying UI field names while changing their meaning.

### Additional normal-user memory checks

An informational DRM_IOCTL_I915_QUERY on the Intel render node succeeded
without changing permissions or settings. It reported one system region:

- Probed bytes: 66,628,472,832.
- Unallocated field: 66,628,472,832.

The equal fields are not evidence of zero graphics allocation: a useful
unallocated value can be withheld without elevated monitoring access.
A separate client snapshot deduplicated nine readable Intel clients:

- Allocated system memory: 218,872 KiB (about 213.7 MiB).
- Resident system memory: 218,872 KiB in this snapshot; this need not always
  equal allocated memory.
- Shared category: 24,584 KiB, already within the allocation, not extra bytes
  to add to it.
- Stolen-local allocation: 0 in the readable entries.

Runtime state was active before and after the query/inventory.
No new encode/decode/render workload was run and no Mission Center UI values
were captured side by side. Source tracing and a capability query do not
establish exact numeric parity with the user's application display.

### Plan revision and preservation

The first block now has four stats: utilization, requested clock, approximate
visible-client memory allocation, and combined video encode/decode.
It follows the existing eight AMD rows, with a spacer/heading, for fourteen
right-column rows at the proposed defaults. Extra engine bars and actual/
media-clock details move to later work; memory usage is explicitly included now.
An exact global memory percentage, isolated power, temperature, and a separate
encode-versus-decode split are not fabricated from the available counters.

Updated PLAN-INTEL-IGPU.md, PLAN.md, CHANGELOG.md, and this audit entry only.
Production source, binaries, installed packages, app settings, user layouts,
permissions, capabilities, and driver bindings were preserved.
Temporary official-source clones and a small memory-query probe were used
only for investigation; none were built into the project.
Validation: source/package inspection, the memory query/client snapshot,
document-link/fence checks, whitespace checks, and protected-file hashes.
No project build or full regression suite was run for these documentation edits.
The four docs remain uncommitted; no push or installation was performed.
In progress is back to nobody; implementation has not started.


## Intel iGPU implementation and validation

Date: 2026-10-29 (America/Phoenix). Codex.
Scope: user requested committing/pushing the revised plan first, then implementing
the Mission Center baseline: utilization, clock, memory, video encode/decode.
No new unresolved defect findings in this scoped validation. Finding 7 remains
deferred; the validation/release limits below remain open.

### Audited versions and changes

- Revised plan committed/pushed to outer `origin/main` as
  `b145c76657dea3549f8f8512811efaec347b9abd` before source implementation.
- Source baseline remains `61c598b1a128e06864a4f071347d6ed63ce71282` on
  `amdgpu-meters`; the audited implementation is the uncommitted working tree.
  Installed package remains htop-gpu 3.5.3-8; stock htop 3.5.3-1.1.
- New source: `linux/IntelGPU.{c,h}`, `linux/IntelGPUMeter.{c,h}`.
  Existing source edits: only Makefile list entries and Platform include/registry
  lines. Upstream GPU accumulator, process columns, AMD/RAPL code are unchanged.
- New tests: `tools/intel-gpu-sample.c`, `tools/test-intel-gpu.py`.
  Style gate includes the new driver; AGENTS.md documents the Intel suite.
  No new production command, library, daemon, elevated access, or runtime package.

### Implemented behavior reviewed

Discovery finds the supported i915 `8086:7d67` device, its DRM card/render device
numbers, and GT0 dynamically; no boot-specific card/render number is compiled in.
Selection is deterministic by PCI address. Node identity/driver/PCI checks exclude
AMD fdinfo. Device/card changes invalidate previous samples. No render node is
opened by the sampler, and runtime status is checked before dynamic reads.

All meters share a newer-tick cache. Histories are per 64-bit DRM client ID under
the selected PCI device, globally deduplicated across FDs and processes.
Independent engine baselines, elapsed monotonic time, counter high-water marks,
capacity changes, missing reads, expired clients, and reappearance are handled
without using a new client's lifetime work as its current interval.
Raw render/compute/video rates and video capacity remain available in the sample.
The utilization index is capped render+compute; video is one capped shared E/D
engine-equivalent index, with no division by two for the display convention.

Clock uses requested GT0 MHz and rereads its mutable configured maximum.
Memory sums valid allocated `drm-total-system0` bytes once per visible client,
with checked unit conversion/overflow. It does not add resident/shared counters.
Memory text and LED show approximate absolute usage; bar/graph modes are omitted
because no validated global denominator exists. Shared objects can overlap across
different client IDs. Missing fields/access are distinguished from known zero.
The heading says visible apps, with known partial/no-access status. Inaccessible
process directories are counted as coverage limits, not presumed GPU clients.

### Failures traced and corrected during development

1. The initial decode workload failed with an `Operation not permitted` seek
   error when looping raw H.264. Intel video counters still responded, but the
   fixture itself was invalid. Replaced it with a temporary MP4 and a single
   five-second decode. Final pinned encode and decode both exited 0, no stderr.
   No permission or production-code workaround was needed for this test error.
2. An initial 5% accounting tolerance caused intermittent N/A during valid Intel
   graphics load. A traced interval reported about 446 ms render time over
   410 ms wall time. Driver updates are not synchronized to sampler timestamps.
   The final plausibility guard allows bounded 25% mismatch plus rounding while
   rejecting gross jumps; display saturation remains separate. A 110% fake
   regression retains raw 110 and displays 100. The follow-up live trace had
   14 valid post-baseline intervals, raw render 92.38–109.38%, no N/A gaps.
3. Final review found invalid/conflicting video capacity could leave misleading
   capacity metadata even while activity was unavailable. It now reports zero
   (unavailable). The exact final source passed fake tests/negative controls and
   a full sanitized htop display smoke after this correction.

These issues were resolved before handoff; none is an outstanding audit finding.

### Validation completed

- Normal htop build: exit 0, zero warnings. Initial float-ID comparison warnings
  were removed by parsing vendor/device IDs as integers.
- `tools/check-style.sh`: `STYLE OK`, including all four new source/header files
  and the new standalone driver. `tools/test-check-style.sh`: all seven passed.
- `python3 -I tools/test-intel-gpu.py --mutations`: `ALL PASSED` under ASan/UBSan.
  Ten stateful fake scenarios cover activity/cache, allocated versus resident
  memory, global fork/FD deduplication, AMD/other-PCI filtering, 64-bit IDs,
  valid timing overshoot, video capacity/default/change/malformed/recovery,
  discovery/unbind/rebind/card renumbering, suspend/wake, backwards counters,
  corrupt jumps, missing fields/client exit/reuse, units/overflow, access loss,
  zero/missing/requested-versus-actual clocks, and mutable maxima.
  Three negative controls fail when device filtering, global deduplication,
  or dual-video capacity handling is deliberately broken.
- Live workloads pinned to Intel: five-second VA-API encode peaked at 32.7%
  video, decode at 18.7%, and an offscreen Vulkan graphics workload reached 100%
  utilization. Valid allocated memory and requested clock/max were observed
  for each; GT0 requested 2000 MHz under graphics load. Workloads exited 0 and
  the sanitized sampler had no diagnostics. No real user media was used.
- `python3 -I tools/test-sampler.py`: `ALL PASSED`; AMD encode reached 100%
  video, 2933/2200 MHz video clocks, sanitizer clean.
- `python3 -I tools/test-rapl.py`: `ALL PASSED`; live pre-load/busy readings
  26.315/130.022 W. Concurrent activity makes these observations, not a benchmark.
- `tools/test-config-path.sh`: all 33 checks passed using disposable homes.
  No production config-handling change was made.
- Whole htop ASan/UBSan build and normal rebuild: zero warnings. Production
  Intel meters ran in one sanitized fake-root process through nine display
  stages: initial, changed, invalid/missing, zero recovered, sleep, wake,
  known-Intel-FD partial denial, whole-proc denial, and final recovery.
  Tested bar/text/graph/LED where supported, memory text/LED, and text heading.
  Clock/memory values changed and cleared correctly; no-access retained valid
  clock text; sleep cleared old values. Process exit 0, no sanitizer reports.
- Exact final source: repeated fake-only suite with all negative controls,
  style, normal build, and sanitized whole-program display smoke passed.
  No live repeat after the final capacity-metadata correction because the user
  asked about playing a game; the corrected path is exercised by fake tests.
- Actual disposable third-column capture retained eight AMD rows, then spacer,
  Intel heading and four stats: 100% utilization, 2000 MHz requested,
  approximately 272 MiB allocated, and 0% E/D during the graphics workload.
  Preview is `test/intel-igpu-preview.rc` with capture `.txt` (ignored artifacts).
- One short CPU-cost observation, same copied base layout: installed build
  used 0.168 CPU seconds over 6.090 seconds; development with Intel block used
  0.270 over 6.082 seconds, about 1.7 additional percentage points of one core.
  Sanitized standalone scanning under graphics load had median 11.008 ms,
  maximum 14.046 ms. These uncontrolled short observations do not establish a
  stable overhead guarantee, especially with other desktop/game activity.

### Limits, preservation, and handoff

Real runtime suspend was observed before initial graphics sampling, and fake
suspend uses a blocking clock FIFO to prove dynamic files are skipped.
A later passive PM observation was inconclusive: the iGPU became active before
the sampler started and stayed active during the observation. External activity
was not isolated. Kernel v7.3 `intel_rps_read_punit_req` uses runtime-PM-if-in-use
for requested frequency, but source inspection and fake tests do not prove an
isolated real idle/suspend result. No forced PM state or power settings changed.

No side-by-side Mission Center UI comparison, isolated compute workload, or
copy/enhancement workload was performed. Reference-source semantics were checked
in the preceding planning audit. Activity covers readable clients; short-lived,
hidden, or raced clients can be omitted. Memory is approximate allocation, not
unique device-wide resident bytes. Separate encode/decode, PMU, xe/other PCI IDs,
actual/media clocks, isolated power/temperature, and finding 7 remain deferred.
Terminal captures check content and state changes, not interactive F2 operation
or pixel-level graph/LED appearance.

Baseline fingerprints covered 403 files. The final preservation check permits
only the documented outer docs/style tool and nested registration edits among
those baseline files; new implementation/tests are additional files. Installed
binaries, stock files, both real user configs, existing AMD/RAPL sources, and
packaging were preserved. No settings, drivers, sysctls, udev rules, capabilities,
packages, or live layout were changed. All temporary GPU workloads finished
before the promise to avoid further GPU load while the user plays Dune Awakening.

Only the revised plan was committed/pushed. Implementation/tests/handoff docs
remain uncommitted; no patch export, package build, installation, or real-layout
edit. Normal development binary is rebuilt. Next step is review/release when
requested, plus the remaining real PM/reference comparison checks.
PLAN.md/CHANGELOG.md updated; in progress nobody.


## Intel iGPU release: install and user layout

Date: 2026-10-29 (America/Phoenix). Codex.
Scope: the user authorized installing the Intel build and updating the actual
htop-gpu rc to display Intel underneath AMD. No new defect findings in this
release validation. Previous real-PM/reference-comparison limits and deferred
finding 7 remain unchanged.

### Packaged source and verification

- Installed before: htop-gpu 3.5.3-8; source HEAD
  `61c598b1a128e06864a4f071347d6ed63ce71282` plus the Intel working tree reviewed
  in the preceding audit. No production source changed during this release.
- New package: `packaging/htop-gpu-3.5.3-9-x86_64.pkg.tar.zst`.
  PKGBUILD pkgrel is 9, description mentions Intel, and checksums include patch
  `0010-linux-add-Intel-iGPU-meters.patch`. The first nine patches are unchanged.
- Patch 0010 captures the six-file working-tree change (four new Intel files,
  Makefile and Platform registration). Used a separate temporary Git index;
  neither real index/history was changed. No commit or push for this request.
  Commit the Intel source before running `tools/export-patches.sh` again,
  since that tool exports commits and would omit uncommitted Intel code.
- Applied all ten patches to upstream 3.5.3 in a disposable tree: clean apply,
  all 368 source files exactly match the current development tree.
- `MAKEFLAGS=-j2 makepkg -fC --holdver --noconfirm`: exit 0, zero compiler
  warnings/errors. Existing local source cache used. PKGBUILD SHA-256 matches
  the built package's `.BUILDINFO`; packaged version is `htop 3.5.3-9-gpu`.
- `python3 -I tools/test-intel-gpu.py --fake-only --mutations`: `ALL PASSED`
  including all three deliberate fault controls, ASan/UBSan clean.
  `tools/check-style.sh`: `STYLE OK`.
- Extracted package binary passed all 33 `tools/test-config-path.sh` checks
  in disposable homes and rendered the proposed third column. All Intel meter
  names persisted after saving the disposable config.
- No package file paths overlap stock htop's files. Namcap matches the stock
  package's existing hicolor-icon-theme dependency, implicit glibc, and possibly
  unneeded libnl diagnostics. Stock additionally reports its GPL license-format
  issue. No new package diagnostic was introduced by Intel support.

### Installation and actual config change

Noninteractive sudo required a password. Desktop authentication via pkexec
completed the package-manager upgrade from 3.5.3-8 to 3.5.3-9, exit 0.
Installed `/usr/bin/htop-gpu` exactly matches the extracted package binary.
`pacman -Qkk htop-gpu htop`: both have 16 total files and zero altered files.
Stock htop remains 3.5.3-1.1.

Checked for htop/htop-gpu processes before backing up and immediately before
atomic replacement; none were running. Backup, byte-for-byte verified:
`/home/pieman/.config/htop-gpu/htop-gpurc.bak-2026-10-29_14-47-46`.

Only these two lines changed in the real rc:

```text
column_meters_2=AMDGPUUsage AMDGPUVRAM AMDGPUPower AMDGPUVideo AMDGPUFan AMDGPUTemp AMDGPUClock AMDGPUMemClock Blank IntelGPUInfo IntelGPUUsage IntelGPUClock IntelGPUMemory IntelGPUVideo
column_meter_modes_2=1 1 1 1 1 2 2 2 2 2 1 2 2 1
```

This keeps all eight AMD rows and adds spacer, scope heading, utilization bar,
requested-clock text, approximate-memory text, and combined E/D bar. The right
column has fourteen rows; the other columns and all other settings are intact.
File permissions are preserved; stock htop's config is unchanged.

An installed-binary capture using a disposable copy verified AMD rows followed
by all five Intel entries. That observation showed 0% Intel utilization,
0 MHz requested, approximately 175 MiB allocated, and 0% E/D. These are passive
readings while other activity was running, not a new load test or proof of
device-wide idle. The actual rc remained byte-identical to the intended change
after the capture; test execution did not rewrite it.

### Preservation and limits

Release baseline fingerprints covered 407 files. Only documented outer release
docs/PKGBUILD, the installed htop-gpu binary, and the two-line real htop-gpu rc
change differ among those baseline files. Stock files/config, preexisting
production source/test tools, and the nine prior patches are unchanged.
New patch 0010 and the config backup are additional files. Package integrity
checks validate the installed package files.

No additional GPU load, isolated PM check, or Mission Center comparison was
performed during this release, honoring the gaming-session constraint.
The prior live/render/video and full sanitized meter evidence covers the same
source; the release added fake/stateful/style, packaging, config, integrity,
and passive display checks. No driver, capability, permission rule, sysctl,
or GPU setting changes. Package-manager cache/desktop hooks ran normally.

Local evidence/receipt (ignored): `test/intel-igpu-release-2026-10-29/`.
Source implementation, tests/docs, PKGBUILD, and patch 0010 remain uncommitted;
no push. Installation and requested layout update are complete.
PLAN.md, PLAN-INTEL-IGPU.md, AGENTS.md and CHANGELOG.md reflect the release;
in progress nobody.


## Intel readout refinement: clock and memory

Date: 2026-10-29 (America/Phoenix). Codex.
Scope: user requested frequency without `requested`, and memory amount without
`~` / `allocated`. No new findings from this scoped display/release validation.
Prior real-PM/reference-comparison limits and deferred finding 7 are unchanged.

### Audited change

- Before: installed htop-gpu 3.5.3-9; source HEAD `61c598b1` plus the existing
  uncommitted Intel implementation. After: installed htop-gpu 3.5.3-10.
- Only two production format strings changed in `linux/IntelGPUMeter.c`:
  `%.0fMHz requested` to `%.0fMHz`, and `~%s allocated` to `%s`.
  Values, units, sensor sources, validity, modes, scale, captions, and internal
  names are unchanged. Requested GT0 clock and approximate visible-client
  allocated memory remain explained in meter descriptions and project docs.
- Updated the same working-tree packaging patch 0010, pkgrel 10, and its checksum.
  Used a separate temporary index; real indexes/history unchanged. No commit/push.
  Previous Intel implementation/tests/docs remain uncommitted as recorded above.

### Validation and installation

- Normal development build: exit 0, zero warnings.
- `tools/check-style.sh`: `STYLE OK`.
  `python3 -I tools/test-intel-gpu.py --fake-only --mutations`: `ALL PASSED`,
  including three deliberate fault controls, ASan/UBSan clean.
- Updated the changed meter in the previously built complete sanitized htop
  tree with ASan/UBSan compile/link flags, zero warnings. A disposable-copy
  header capture with fake Intel readings displayed `iGPU clock: 800MHz` and
  `iGPU mem: 4.00M`, with all three removed qualifiers absent from those rows.
  No sanitizer diagnostics. This was an incremental update of the full-program
  sanitized build, not a fresh clean rebuild of unchanged modules.
- `MAKEFLAGS=-j2 makepkg -fC --holdver --noconfirm`: exit 0, zero compiler
  warnings/errors. All ten patches applied cleanly to upstream 3.5.3 and exactly
  reproduced all 368 source files. No package paths overlap stock htop.
- Namcap reports the same known stock-baseline hicolor-icon-theme, implicit
  glibc, and possibly unneeded libnl diagnostics; no new diagnostics.
- Extracted package reports `htop 3.5.3-10-gpu`. Passive display capture with
  a copy of the actual config showed `iGPU clock: 0MHz`, `iGPU mem: 170M`.
  No `requested`, tilde, or `allocated` in those readouts.
- Installed via the desktop authentication/package-manager path, exit 0.
  Installed binary exactly matches the extracted package binary.
  `pacman -Qkk htop-gpu htop`: 16 total files each, zero altered files.
  Stock htop remains 3.5.3-1.1.
- Installed display checked again with a disposable rc copy; all Intel rows
  render and clock/memory have the shortened formats. The receipt stores the
  observed values and package/binary fingerprints.

### Preservation and limits

Baseline fingerprints cover 414 tracked/untracked project source/tool/doc files,
stock htop files, installed binary, and both user configs. Only the two-string
meter edit, patch 0010/PKGBUILD, installed binary, and release docs changed.
The sampler, existing test tools, prior nine patches, stock files, both real rc
files, and the current AMD/Intel layout are unchanged.
No config edit or new backup was necessary for these text-only changes.

No new tests were added for the two format strings. Reused existing stateful
fake tests and actual program captures. No additional GPU workload was run,
honoring the gaming-session constraint. The full AMD/live Intel/RAPL/config
suites and fresh full clean sanitizer build were not repeated for this display
change; their earlier evidence covers the unchanged sampling/config code.
No new device-wide memory accuracy or actual-clock claim is made by shortening
the readouts. No driver, permission rule, sysctl, or GPU setting changes.

Local evidence/receipt (ignored): `test/intel-labels-release-2026-10-29/`.
PLAN.md, PLAN-INTEL-IGPU.md, AGENTS.md and CHANGELOG.md updated; in progress nobody.


## Intel heading refinement

Date: 2026-10-29 (America/Phoenix). Codex.
Scope: user requested just `Intel iGPU` without `visible apps`; sleep is retained.
No new findings from this scoped display/release validation. Previous real-PM/
reference-comparison limits and deferred finding 7 remain unchanged.

### Change and audited versions

- Before: installed 3.5.3-10. After: installed htop-gpu 3.5.3-11. Source HEAD
  remains `61c598b1` with the existing uncommitted Intel implementation.
- Only heading formatting changed in `linux/IntelGPUMeter.c`: normal text is
  `Intel iGPU`, without a colon or visible-app/partial suffix. Sleep remains
  `Intel iGPU: sleep`; no-access/unavailable status remains. Explicitly clear
  the text buffer on normal active samples so old status text cannot linger.
- Readable-app coverage remains in meter descriptions. Sampler behavior, numeric
  readouts, meter names/modes, both real configs, and the saved layout are unchanged.
- Updated working-tree patch 0010, PKGBUILD pkgrel 11, and checksum via a temporary
  index. No real staging, commit, or push; previous uncommitted work remains.

### Validation

- Normal build: zero warnings. Updated the changed meter in the previously built
  full ASan/UBSan htop tree with sanitizer compile/link flags, zero warnings.
- `tools/check-style.sh`: `STYLE OK`. Intel fake/stateful tests with all three
  negative controls: `ALL PASSED`, ASan/UBSan clean.
- One complete sanitized htop process ran five heading transitions: active
  `Intel iGPU` → `Intel iGPU: sleep` → `Intel iGPU` → `Intel iGPU: no access`
  → `Intel iGPU`. Correct text and suffix clearing throughout; exit 0, no
  sanitizer diagnostics. Temporary fake runtime/proc-permission changes restored.
- `MAKEFLAGS=-j2 makepkg -fC --holdver --noconfirm`: exit 0, zero warnings/errors.
  All ten patches apply cleanly to upstream 3.5.3 and reproduce all 368 source
  files exactly. No package paths overlap stock htop. Namcap reports only the
  established stock-baseline hicolor-icon-theme/glibc/libnl diagnostics.
- Packaged binary reports `htop 3.5.3-11-gpu`. Disposable-copy display confirms
  the shortened heading/sleep indication with AMD/Intel placement unchanged.
- Package-manager upgrade through desktop authentication: exit 0. Installed
  binary exactly matches the package; installed-copy display has no visible-app
  suffix. Receipt records the observed state. Both htop packages have 16 files
  and zero altered files; stock htop remains 3.5.3-1.1.

### Preservation and limits

Baseline fingerprints cover 414 project/source/stock/config files. Only the
heading source, patch 0010/PKGBUILD, installed htop-gpu binary, and release docs
changed. Sampler, previous nine patches, existing tests/tools, stock htop files,
and both real rc files are preserved. No config edit/new backup was needed.
No new permanent tests for this small UI change; used existing fake tests and
actual stateful program captures. No added GPU workload during the gaming
session. Unrelated full AMD/RAPL/config/live suites and a fresh clean sanitizer
rebuild were not repeated; prior results cover their unchanged code.
No driver, sysctl, capability, permission rule, or GPU setting changes.

Local evidence/receipt (ignored): `test/intel-heading-release-2026-10-29/`.
Docs and shared status updated; in progress nobody. Source/tests/docs/packaging
remain uncommitted, with no push. Restart htop-gpu to load the updated executable.


## Intel iGPU audit: installed 3.5.3-11

Date: 2026-10-29 (America/Phoenix). Codex.
Scope: complete Intel sampler/meters/tests/registration/package review after the
requested readout/heading refinements. One new P2 finding; no production fix.

### Baseline and reviewed behavior

- Outer HEAD `b145c76657dea3549f8f8512811efaec347b9abd`; source HEAD
  `61c598b1a128e06864a4f071347d6ed63ce71282`, with the existing uncommitted Intel
  implementation/refinements. Installed htop-gpu 3.5.3-11, stock htop 3.5.3-1.1.
- Read project handoff and upstream instructions/style, current Intel plan,
  new source/header files, standalone driver/test suite, existing Meter/Compat
  behavior, registration, patch 0010, and package metadata.
- Reviewed device/PCI filtering, global client deduplication, cache, independent
  engine deltas/high-water marks, capacity guards, expiry/rebind/suspend handling,
  checked memory accounting, requested clock/max scaling, and supported modes.
  Independent read-only meter/test/package review found no additional defects.
- The user's compact heading/readouts are intentional. Readable-client scope,
  allocated-memory approximation, combined E/D convention, and requested clock
  are documented constraints, not new defects. Uncommitted-source packaging
  and remaining real-PM/Mission Center comparisons are already documented.

## 8. [P2] Lost access to a known Intel client can appear as zero usage

Status: fixed and validated in installed 3.5.3-12; the reproduction below is the
original 3.5.3-11 behavior. See the subsequent finding 8 fix validation.

Primary location: `src/htop/linux/IntelGPU.c:478-481`.
Related paths: fd stat filtering at lines 363-370 and 487-489; unseen-client
cleanup at lines 383-386; empty-client output at lines 437-452.

### Reproduction and impact

The exact source was compiled with ASan/UBSan against a private fake sysfs/proc
root. Each case kept one sampler running across transitions. A readable Intel
client first reported 10% utilization and 1,048,576 allocated bytes. Then:

| Transition at the next newer tick | Clients | Denied | Incomplete | Usage | Memory |
| --- | ---: | ---: | --- | ---: | ---: |
| That process's fdinfo directory becomes inaccessible | 0 | 1 | false | 0% | 0 bytes |
| Its fd directory becomes inaccessible before node stat | 0 | 0 | false | 0% | 0 bytes |
| Control: the process really exits | 0 | 0 | false | 0% | 0 bytes |

The two denial cases are therefore presented like the valid exit case. Restored
access rebaselines and eventually recovers the values. The process remains in
the fake proc tree throughout denial; this is not a client-exit reproduction.
All sampler processes exited 0 without sanitizer diagnostics.

The actual production meters in one private full sanitized htop process also
reproduced `iGPU mem: 4.00M` → `iGPU mem: 0K` → `iGPU mem: 4.00M` on directory
denial/recovery. The heading remained the intended `Intel iGPU`; no error was
shown for this lost coverage. This is a misleading availability/zero transition,
not a crash, system-setting change, or measured loss of real GPU allocation.

A separate real-host probe used a throwaway child that opened only `/dev/null`.
Toggling its own PR_SET_DUMPABLE produced readable → denied → readable access
to its fdinfo directory while it remained alive. No Intel/AMD DRM node was
opened. This establishes that the directory-access transition is possible on
this kernel; the full GPU accounting case was reproduced with fake data.
Independent fd-stat-only denial is an additional fake failure path, not a claim
that ordinary host DAC commonly denies it while fdinfo remains readable.
Linux documents the [dumpability effect on proc ownership](https://man7.org/linux/man-pages/man2/PR_SET_DUMPABLE.2const.html)
and [fdinfo access](https://man7.org/linux/man-pages/man5/proc_pid_fdinfo.5.html).

### Cause and suggested correction

Directory-open denial increments `denied` but does not mark loss of a previously
identified client's data. Node stat failures are silently treated as a non-DRM
file. Unobserved client records are then freed; an otherwise readable proc scan
with no observed clients becomes valid zero activity/memory. By contrast, a
denied fdinfo *file* after successful Intel node identification correctly sets
`incomplete` and avoids this false zero.

Retain enough process/client ownership information to distinguish inaccessible
previously identified Intel clients from ordinary exits, unrelated protected
processes, and PID reuse. Propagate unknown/incomplete coverage where a known
client cannot be sampled; recover with a safe baseline. Account for a shared
client that is still readable through another process/descriptor. Do not mark
every denied process incomplete: many protected processes were never identified
as Intel clients and are part of the deliberate readable-client scope.

Add stateful tests for known-client fdinfo-directory denial, node-stat denial,
recovery, actual exit, unrelated protected processes, and shared-client coverage.
The current access suite tests a denied fdinfo file and an entirely denied proc
root, so it passes without exercising this intermediate-directory gap.

### Other validation and limits

- Existing `python3 -I tools/test-intel-gpu.py --fake-only --mutations`: all ten
  fake scenarios and three deliberate fault controls `ALL PASSED`, ASan/UBSan
  clean. The additional audit probes establish finding 8 despite that pass.
- `tools/check-style.sh`: `STYLE OK`; normal development build: exit 0, no new
  warnings. Private incremental full sanitized-program build: exit 0, zero
  warnings; display reproduction exited 0 with no sanitizer logs. It reused
  previously sanitized unchanged modules rather than doing a new clean build.
- Ten patch checksums passed. PKGBUILD fingerprint matches package `.BUILDINFO`;
  installed binary exactly matches the packaged one. Both installed htop packages
  have 16 files and zero altered files. No new release or reinstall was performed.
- Passive host inventory found ten unique readable Intel clients, no missing
  render/compute/video/allocated-memory keys, video capacity two, and 418 denied
  fdinfo directories. Those denied directories are not presumed Intel clients
  and do not demonstrate finding 8 occurring in the user's current workload.
- The [DRM usage-statistics ABI](https://docs.kernel.org/gpu/drm-usage-stats.html)
  was checked for identity/deduplication, backward counters, capacities, and
  allocated/resident semantics. No additional actionable defects were identified.
- No new GPU load, isolated PM experiment, or side-by-side Mission Center run.
  Fresh live Intel/AMD/RAPL workloads, unrelated full config suite, interactive
  F2 testing, and a clean full sanitizer rebuild were not performed in this
  read-only audit. Earlier live results remain historical evidence.

### Preservation and handoff

Baseline fingerprints cover 418 project/source/tool/config/installed files.
Only AUDIT.md, PLAN.md, PLAN-INTEL-IGPU.md, and CHANGELOG.md changed. Private
probes and captures are ignored under `test/intel-audit-2026-10-29/`. No production
source/test, packaging, installed binary, real config/layout, driver setting,
sysctl, udev/capability rule, or other user process was changed. The disposable
child changed only its own dumpability and exited normally.

Finding 8 remains open; no fix, installation, commit, or push. Finding 7 stays
deferred. All previous uncommitted implementation/release work remains intact.
Shared handoff updated; in progress nobody.


## Finding 8: fix, validation, and installation

Date: 2026-10-29 (America/Phoenix). Codex.
User authorized fixing finding 8. Status: resolved and validated in installed
htop-gpu 3.5.3-12. Finding 7 remains deferred; no new unresolved finding from this fix.

### Versions and implementation

- Source baseline remains `61c598b1a128e06864a4f071347d6ed63ce71282` plus the
  existing uncommitted Intel implementation. Before this fix: installed 3.5.3-11.
  New production changes are confined to `linux/IntelGPU.c`; tests extend
  `tools/test-intel-gpu.py`. No meter formatting or public sample API changes.
- Track known PID/starttime/FD-to-client references separately from rate history.
  Process-stat field 22 identifies PID generations, parsing comm names containing
  spaces/parentheses safely. Failed identity reads retain uncertain knowledge; a
  confirmed new starttime invalidates old ownership.
- Directory-open denial and FD-stat permission failure preserve known-client
  uncertainty across repeated ticks. Whole-proc denial resets rate baselines
  while retaining ownership for later scans. Missing known data makes activity
  and empty memory unavailable instead of fabricating zero. Known allocated
  totals from other readable clients remain approximate lower-bound data.
- A client still readable through another owner is counted once and supplies
  valid readings. Confirmed FD close, process exit, and PID reuse expire obsolete
  references. Per-FD tracking prevents an unrelated denied FD in the same process
  from retaining a closed Intel FD. Device generation/removal clears both maps.
- Ownership is allocated only for identified Intel processes/FDs; ordinary
  protected processes are not presumed GPU clients. References are bounded to
  observed FD associations, with closed FDs/processes pruned after readable scans.

### Regression and actual-meter validation

- Stable fake `/proc/PID/stat` fixtures added; existing counter updates preserve
  process generation. Added eight stateful groups, for 18 total. Coverage includes
  process fdinfo-directory denial, FD-stat denial, repeated denial, recovery,
  real exits, unrelated protected processes/FDs, shared readable aliases and
  their loss, PID reuse, missing/malformed identity, and whole-proc recovery while
  a known child remains inaccessible. Each scenario keeps one sampler running.
- Fixed source: `python3 -I tools/test-intel-gpu.py --fake-only --mutations`
  reports `ALL PASSED`: 143 passing checks including the three original deliberate
  PCI/deduplication/capacity fault controls. ASan/UBSan clean.
- The exact saved pre-fix source fails ten new assertions with the updated
  fixtures, proving these tests expose the previously passing access-loss gap.
- Normal development build and `tools/check-style.sh`: zero warnings, `STYLE OK`.
  Source lifecycle review found no additional blocking issue in this fix.
- Updated the sampler in a private complete sanitized htop copy with the exact
  current feature sources and private fake roots. Six transitions in one process:
  readable 4.00M → directory denied N/A → still denied N/A → recovered 4.00M
  → FD-stat denied N/A → recovered 4.00M. Activity/video also show N/A during lost
  coverage. Exit 0; no sanitizer diagnostics. This reused unchanged previously
  sanitized modules, rather than rebuilding all modules from a clean tree.
- Passive real-host sampler: suspended → unavailable during a transition →
  active; active samples found 16 readable clients and 438 denied directories,
  incomplete=false, about 184 MiB allocated, valid idle deltas after baseline.
  The denied directories were not presumed Intel clients. No DRM device was
  opened and no GPU workload was generated by the probe. ASan/UBSan clean.
  Three active sanitized reads took 23.9–27.1 ms under existing system activity;
  this short uncontrolled observation is not a performance benchmark or PM proof.

### Package and installed validation

- Updated the existing working-tree patch 0010 and checksum, pkgrel 12. Used a
  private temporary Git index; real indexes/history unchanged. No commit/push.
- `MAKEFLAGS=-j2 makepkg -fC --holdver --noconfirm`: exit 0, zero compiler
  warnings/errors. All ten patches apply to upstream 3.5.3 and exactly reproduce
  all 368 current source files. No package paths overlap stock htop.
- Namcap matches the established stock-baseline hicolor-icon-theme, implicit
  glibc, and possibly unneeded libnl diagnostics; no new diagnostics.
- Package and installed captures using disposable real-layout copies preserve
  the eight AMD rows followed by Intel and the user's compact heading/readouts.
  No real config was rewritten for these checks.
- Installed 3.5.3-12 via desktop authentication/package manager, exit 0. Installed
  binary exactly matches the extracted package. `pacman -Qkk htop-gpu htop`: both
  have 16 files and zero altered files. Stock htop remains 3.5.3-1.1.

### Preservation, testing limits, and handoff

Baseline fingerprints cover 418 project/source/tool/config/installed files. Only
the documented sampler/test, working-tree patch/PKGBUILD, installed htop-gpu
binary/manual, and five release/handoff docs changed. The manual differs only
in its version header (3.5.3-11-gpu → 3.5.3-12-gpu) and exactly matches the package.
Real htop-gpu/stock configs and
layout, previous nine patches, other production sources/tools, and stock htop
files are preserved. No driver, sysctl, udev/capability rule, or GPU setting changes.

No new Intel/AMD/RAPL load tests were run, honoring the gaming-session constraint.
Full unrelated config tests, isolated real PM measurement, side-by-side Mission
Center comparison, interactive F2 behavior, and a fresh clean full sanitizer
build were not repeated. Low-level readdir I/O errors versus clean EOF were not
injected; this fix/test set targets the reproduced directory/stat permission
failures and their lifecycle, not every possible procfs I/O failure.

Local evidence/receipt (ignored): `test/intel-finding8-fix-2026-10-29/`.
Finding 8 is resolved; source/test/docs/packaging remain uncommitted with previous
work intact. No push. Shared docs updated; in progress nobody. Restart htop-gpu
to load the fixed executable.


## Review of the Intel iGPU work by Claude Code

Date: 2026-10-29. Reviewed and committed at the user's request ("review it and commit / push if it looks good").
Baseline: outer `b145c76` plus Codex's uncommitted Intel work, htop `61c598b1` plus the uncommitted `linux/IntelGPU*` files; installed `htop-gpu 3.5.3-12`.

- Code review of `linux/IntelGPU.c` and `linux/IntelGPUMeter.c`: metadata-only device discovery (no DRM node opened), per-client deduplication, delta baselines, PID/start-time/fd ownership kept across access gaps (finding 8), suspend/rebind/access states, checked memory units, overflow guards, clock limit read every refresh. No defects found. Notes, not findings: the device ID `0x7d67` is hardcoded inline rather than in a card table; `IntelGPU_parse()` returns `int` but uses `false` for its "not this device" case.
- Independent checks: normal build with zero warnings, `STYLE OK`, and `ALL PASSED` from `test-intel-gpu.py --mutations` (19 groups, live encode peak 33.5%, decode 18.7%, graphics 100%), `test-sampler.py`, `test-rapl.py`, `test-config-path.sh` and `test-check-style.sh`.
- Cost: the installed binary used 2.47% of one core over 30 s with the user's layout minus the Intel meters, and 2.87% with them (1.5 s refresh), so the /proc fdinfo pass costs about 0.4% of a core.
- Committed as htop `bb4f7331` (`linux: add Intel iGPU meters`, crediting Codex) and re-exported the series; the new patch 0010 differs from Codex's working-tree patch only in abbreviated vs full `index` blob hashes, so the installed 3.5.3-12 matches the committed code and was not rebuilt.
- No new findings.
