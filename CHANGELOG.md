# htop-gpu changelog

Newest first. One entry per agent session: date, agent, what changed, check
results, anything left half done, what's next. See `AGENTS.md` for the rules.

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
