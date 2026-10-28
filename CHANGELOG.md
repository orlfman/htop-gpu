# htop-gpu changelog

Newest first. One entry per agent session: date, agent, what changed, check
results, anything left half done, what's next. See `AGENTS.md` for the rules.

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
