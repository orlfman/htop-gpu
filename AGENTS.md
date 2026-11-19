# htop-gpu: agent guide

Shared instructions for every AI agent working on this project. Codex reads this
file directly; Claude Code reads it through `CLAUDE.md`. Anything an agent needs
to know lives in this folder, never only in one agent's private memory.

## What this is

A personal custom build of htop 3.5.3 with header meters for AMD dedicated cards
(RDNA 2, 3 and 4: RX 6000, 7000 and 9000; developed and tested on an RX 9070 XT,
the others only against fake sysfs trees; htop `f842f486`, `7c2fe84b`, `943464c0`, `c3a0d73c`; installed as
3.5.3-17):
GPU usage, VRAM, power, edge/junction/memory temperatures, GPU clock, VRAM clock,
video engine. Not meant for upstream htop, but kept as close to upstream as
possible so new htop releases are easy to rebase onto.
The installed build also has heading meters (`AMDGPUInfo` with the card's
name, `IntelCPUInfo` with the CPU model; htop `44265679`, `798d8cfa`) and
Intel i915 meters for this machine's iGPU:
visible-app utilization, requested clock, approximate allocated memory, and
combined video encode/decode. See `PLAN-INTEL-IGPU.md` for scope and release status.
Clock/memory readouts show only the frequency/amount; their meter descriptions
retain the requested-clock and approximate-allocation source details.
The heading is `Intel iGPU` during normal use; sleep and access/error indications
remain. Readable-app coverage is explained in meter descriptions, not the heading.
Finding 8 is fixed: known Intel PID/starttime/FD ownership survives access gaps,
so lost access does not become a false zero. Tests cover aliases, exit, and reuse.
The Intel source is committed as `bb4f7331` (reviewed 2026-10-29); patch 0010 is
exported from it like the others.
Committed as htop `c3a0d73c` and packaged as 3.5.3-17 (patch 0016; installed
2026-11-19): the Intel meters cover Tiger Lake, Rocket Lake, Alder
Lake and newer integrated families (109 PCI IDs from the Linux 7.3 lists) on
both `i915` and `xe`, selecting the supported iGPU with the lowest PCI address.
Discrete Intel graphics, including DG1 and Arc, and earlier integrated families
are excluded. Only this machine's `8086:7d67` on `i915` is tested on hardware;
`xe` and the other families are covered by fake sysfs/fdinfo tests. See
AUDIT.md (findings 20-24).

## Read first

1. `PLAN.md`: design, measured card data, rules for staying close to upstream,
   test plan, order of work, and the current status (including who is working).
2. The newest entries in `CHANGELOG.md`: what the last session did and what's next.
3. `src/htop/docs/styleguide.md` and `src/htop/AGENTS.md`: upstream's coding
   rules, which apply here too.

## Layout

- This folder is its own git repo: plan, docs, `tools/`, later `packaging/`.
  Branch `main`, remote `origin` = https://github.com/orlfman/htop-gpu (public since 2026-11-19;
  README and PKGBUILD point at `packaging/`, not at the private htop clone).
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

- After every audit or re-test, record the results in `AUDIT.md` without
  waiting for a separate request. Include findings (or explicitly none),
  the audited version, validation results, and testing limits. This is the
  user's standing instruction from 2026-10-28.
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
- Don't touch the user's config files unless the user asks:
  `~/.config/htop-gpu/htop-gpurc` (htop-gpu, with the GPU column) and
  `~/.config/htop/htoprc` (stock htop). htop rewrites its config file on exit,
  so test runs use `HTOPRC=<this folder>/test/<config>` (`test/` is ignored).
  When the user does ask: back the file up first and make sure no htop is
  running while editing it.
- Installed: `htop-gpu` (`/usr/bin/htop-gpu`, this project) next to the repo
  `htop` (`/usr/bin/htop`). Rebuilding or reinstalling htop-gpu, or changing the
  stock package, needs the user's OK.

## Checks

Run after every change, from this folder:

- Build: `make -C src/htop -j"$(nproc)"`. No new warnings.
- `tools/check-style.sh` must end with `STYLE OK` (IWYU + astyle on htop-gpu's files).
- `python3 -I tools/test-sampler.py` must end with `ALL PASSED` (about 30 s).
- After touching config handling (`Settings.c`): `tools/test-config-path.sh`
  must end with `ALL PASSED` (throwaway home folders; never the user's files).
- After touching `linux/IntelRAPL.c` or its meter: `python3 -I tools/test-rapl.py`
  must end with `ALL PASSED` (fake powercap trees + live idle/busy, ASan/UBSan).
- After touching `linux/IntelGPU.c` or its meters: `python3 -I tools/test-intel-gpu.py --mutations`
  must end with `ALL PASSED` (stateful fake sysfs/proc, negative controls,
  live Intel encode/decode, ASan/UBSan). `--fake-only` skips live workloads.
- After touching the heading meters (`AMDGPUInfo`, `IntelCPUInfo`) or the card
  name: `python3 -I tools/test-headings.py` must end with `ALL PASSED` (about 50 s;
  fake cpuinfo cases, fake card state changes under one running htop, ASan/UBSan).
- After touching `tools/check-style.sh`: `tools/test-check-style.sh` must end
  with `ALL PASSED`. `check-style.sh` exits 2 (`STYLE CHECK FAILED TO RUN`) when
  a tool is missing or broken; that is not a pass.
- After touching `tools/check-upstream.sh`: `tools/test-check-upstream.sh` must
  end with `ALL PASSED` (local stand-in repositories, no network). The checker
  works from a fresh clone: it asks `src/htop`'s `upstream` remote when that
  clone exists, otherwise htop's GitHub repository.
- New tests should change state under one running process where the code keeps
  state across refreshes; restarting per case hides staleness bugs (AUDIT.md).

Visual checks of meters (htop is full-screen, so run it in a terminal you can see):

- Live: `HTOPRC=test/<config> src/htop/htop`, with a throwaway config in `test/`
  that places the meters to check (e.g. one column per meter mode).
- Broken or sleeping card: `python3 -I tools/fake-sysfs.py test/fake-sysfs
  [--suspended | --unbind | --remove PATH | --write PATH=VALUE]`, then
  `tools/build-htop-fake.sh test/fake-sysfs test/htop-fake` and run
  `test/htop-fake` the same way. Rebuilding only the tree needs no new binary.
- Colors: a plain terminal read shows no colors, so use
  `python3 -I tools/htop-capture.py test/<config> <htop binary> [seconds]`, which
  prints each header row with its text grouped by color. An htoprc of `-` leaves
  `HTOPRC` unset, so htop finds its config file itself.
- Sanitizers, after changing meter or sampler code: `tools/build-htop-asan.sh
  test/htop-asan [test/fake-sysfs]` builds the whole htop with ASan + UBSan
  (and rebuilds the normal one). Run it through `htop-capture.py` with
  `ASAN_OPTIONS=log_path=<dir>/asan:detect_leaks=0` and
  `UBSAN_OPTIONS=log_path=<dir>/ubsan:print_stacktrace=1`; no files in `<dir>`
  means no findings.

Packaging, after new commits in `src/htop`: `tools/export-patches.sh`
regenerates `packaging/*.patch` and the PKGBUILD checksums; `makepkg -fC` in
`packaging/` builds; `namcap` on the package should only report what it reports
for the stock htop package. `tools/check-upstream.sh` tells when a newer htop is
out.

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

- The 9070 XT is PCI `0000:04:00.0`, ID `1002:7550` revision `c0`, graphics core
  (GC) 12.0.1 in `ip_discovery`. Cards are recognized by GC version, and named
  from `/usr/share/libdrm/amdgpu.ids`; the sampler test builds with its own ids
  file (`build-sampler.sh` third argument), the htop builds use the system one. `cardN` and `hwmonN` numbers
  change between boots, so code never hardcodes them. `tools/test-sampler.py`
  does assume `0000:04:00.0` for now.
- `/dev/dri/renderD128` is the Intel iGPU. VA-API work on the 9070 XT must use
  `/dev/dri/by-path/pci-0000:04:00.0-render`.
- `amdgpu.runpm=0` is set, so the card never runtime-suspends. The suspended code
  path is covered by the fake-sysfs tests instead.
- The live tests read `/sys` and open `/dev/dri`. If an agent's sandbox blocks
  those, the live part fails because of the sandbox, not the code. Report that
  instead of changing the code or the tests.
