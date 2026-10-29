# htop-gpu audit findings

Date: 2026-10-28 (America/Phoenix).
Auditor: Codex.
Status: all five findings are fixed; findings 1-4 were independently re-tested by Codex, and the finding 5 test fix was applied and validated by Codex.
All findings are P2 (normal priority).

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
