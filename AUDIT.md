# htop-gpu audit findings

Date: 2026-10-28 (America/Phoenix).
Auditor: Codex.
Status: three reproduced issues; no fixes applied.
All three are P2 (normal priority).

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
