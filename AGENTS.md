# htop-gpu: agent guide

Shared instructions for every AI agent working on this project. Codex reads this
file directly; Claude Code reads it through `CLAUDE.md`. Anything an agent needs
to know lives in this folder, never only in one agent's private memory.

## What this is

A personal custom build of htop 3.5.3 with header meters for an AMD RX 9070 XT:
GPU usage, VRAM, power, edge/junction/memory temperatures, GPU clock, VRAM clock,
video engine. Not meant for upstream htop, but kept as close to upstream as
possible so new htop releases are easy to rebase onto.

## Read first

1. `PLAN.md`: design, measured card data, rules for staying close to upstream,
   test plan, order of work, and the current status (including who is working).
2. The newest entries in `CHANGELOG.md`: what the last session did and what's next.
3. `src/htop/docs/styleguide.md` and `src/htop/AGENTS.md`: upstream's coding
   rules, which apply here too.

## Layout

- This folder is its own git repo: plan, docs, `tools/`, later `packaging/`.
  Branch `main`, remote `origin` = https://github.com/orlfman/htop-gpu (private).
- `src/htop` is a separate git clone of htop, branch `amdgpu-meters` on top of tag
  `3.5.3`. All htop code changes are commits there. The outer repo ignores `src/`.
  Remotes: `upstream` = https://github.com/htop-dev/htop, `origin` =
  https://github.com/orlfman/htop (private; a plain repo, not a GitHub fork,
  since GitHub forks can't be private).
- The `gh` CLI is logged in as `orlfman`, and git uses it for github.com over HTTPS.
- `packaging/` (step 5) will hold the PKGBUILD and the patches exported from
  `src/htop` with `git format-patch`.

## Taking turns

Only one agent works on the project at a time.

- Before starting, check "In progress" in the PLAN.md status. If another agent is
  listed, stop and ask the user.
- When starting, set it to `In progress: <agent>, <step>`.
- When finishing or stopping, add a dated entry at the top of `CHANGELOG.md`
  (agent, what changed, check results, anything left half done), update the
  PLAN.md status, and set `In progress: nobody`.
- Uncommitted work left behind must be described in that CHANGELOG entry.

## Rules

- Follow upstream htop's style guide and `src/htop/AGENTS.md`. The only exception:
  no `Signed-off-by:` trailer.
- Keep upstream files nearly untouched. New code goes in new files; existing files
  only get registration lines. Don't reformat or clean up upstream code.
- Commit and push only when the user asks. Never change GitHub repo settings or
  visibility, or create or delete repos, without asking.
- Commits: small and self-contained, each one builds and works, upstream-style
  subjects (`linux: add ...`), descriptive bodies, no merge commits, fixups
  squashed into the commit they fix.
- Every AI-assisted commit ends with a `Co-Authored-By:` trailer naming the agent
  and model, e.g. `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  Other agents use their own name.
- Git identity is set per repo (`orlfman` with the GitHub noreply address). Don't
  change it.
- Ask the user before installing packages, changing system configuration, or
  installing the built htop.
- Never touch `~/.config/htop/htoprc`. htop rewrites its config file on exit, so
  test runs use `HTOPRC=<this folder>/test/htoprc` (a copy; `test/` is ignored).

## Checks

Run after every change, from this folder:

- Build: `make -C src/htop -j"$(nproc)"`. No new warnings.
- `tools/check-style.sh` must end with `STYLE OK` (IWYU + astyle on htop-gpu's files).
- `python3 -I tools/test-sampler.py` must end with `ALL PASSED` (about 30 s).

Visual checks of meters (htop is full-screen, so run it in a terminal you can see):

- Live: `HTOPRC=test/<config> src/htop/htop`, with a throwaway config in `test/`
  that places the meters to check (e.g. one column per meter mode).
- Broken or sleeping card: `python3 -I tools/fake-sysfs.py test/fake-sysfs
  [--suspended | --unbind | --remove PATH | --write PATH=VALUE]`, then
  `tools/build-htop-fake.sh test/fake-sysfs test/htop-fake` and run
  `test/htop-fake` the same way. Rebuilding only the tree needs no new binary.
- Colors: a plain terminal read shows no colors, so use
  `python3 -I tools/htop-capture.py test/<config> <htop binary> [seconds]`, which
  prints each header row with its text grouped by color.

First-time setup when `src/htop/Makefile` is missing:

```
cd src/htop && ./autogen.sh && ./configure --prefix=/usr --sysconfdir=/etc \
    --enable-affinity --enable-capabilities --enable-delayacct --enable-sensors \
    --enable-unicode --enable-debug
```

Needed packages (Arch / CachyOS): base-devel, autoconf, automake, pkgconf,
ncurses, libcap, libnl, lm_sensors, astyle, include-what-you-use, python, ffmpeg,
mesa (VA-API on the 9070 XT).

## Machine facts

- The 9070 XT is PCI `0000:04:00.0`, ID `1002:7550`. `cardN` and `hwmonN` numbers
  change between boots, so code never hardcodes them. `tools/test-sampler.py`
  does assume `0000:04:00.0` for now.
- `/dev/dri/renderD128` is the Intel iGPU. VA-API work on the 9070 XT must use
  `/dev/dri/by-path/pci-0000:04:00.0-render`.
- `amdgpu.runpm=0` is set, so the card never runtime-suspends. The suspended code
  path is covered by the fake-sysfs tests instead.
- The live tests read `/sys` and open `/dev/dri`. If an agent's sandbox blocks
  those, the live part fails because of the sandbox, not the code. Report that
  instead of changing the code or the tests.
