# htop-gpu audit findings

Original audit: 2026-10-28 (America/Phoenix). Latest full project audit: 2026-11-11 (Codex). Latest audit: 2026-11-19 (Claude Code, findings 39–41 fixed and verified).
Auditors: Codex and Claude Code. Newest sections are at the top; the 2026-10-28 audit and older follow-ups start at "Scope and baseline".
Status: findings 1-6 are resolved and validated; finding 6 is committed (`6c06d243`) and retained in installed `htop-gpu 3.5.3-12`, which labels CPU power Pwr. Finding 7 (P3) is deferred at the user's request. Finding 8 (P2, Intel client access loss reported as zero) is fixed and validated in 3.5.3-12; see the fix validation below.
Findings 9-13 (P3, heading meters, Claude Code self-audit 2026-10-29): 9, 10, 11 and 13 are fixed (htop `44265679`, `798d8cfa`; installed in 3.5.3-13), 12 is accepted; see the last two sections.
Finding 14 (P3, heading color-test environment isolation) is fixed and validated locally. See the resolution below.
Findings 15-16 (P2/P3, RDNA 2+ AMD sensor and clock recovery) are fixed and verified (squashed into htop `f842f486` and `7c2fe84b`; packaged in 3.5.3-15).
Findings 17-19 (P2/P3, AMD runtime power state, upstream checker, display-mode docs) are fixed and verified (17 in htop `943464c0`, 18-19 in this repo's tools and docs, outer `bc4e168`; installed in 3.5.3-16).
Findings 20-22 (P2/P3, Xe timestamp stalls, compute-only Xe, live Vulkan device) are fixed and verified (htop `c3a0d73c`, installed in 3.5.3-17 on 2026-11-19).
Finding 23 (P2, generic-only fdinfo on a matched Intel GPU descriptor produces false zeros) is fixed and verified (htop `c3a0d73c`, 3.5.3-17).
Finding 24 (P3, an O_PATH handle on the iGPU node makes usage and video N/A after the finding 23 fix; Claude Code, 2026-11-19) is fixed and verified (htop `c3a0d73c`, 3.5.3-17).
Findings 25-26 (P3, first live xe run on 2026-11-19: refreshes faster than xe's 1 s autosuspend keep an idle iGPU awake; the live graphics check fails on Mesa's xe warning) are fixed and verified in htop `1c205705` (installed in 3.5.3-18). Independently re-verified live on xe by Claude Code.
Finding 27 (P3, Intel meters showed N/A during runtime resume) is fixed and verified in htop `1c205705` (installed in 3.5.3-18). Independently re-verified live on xe by Claude Code.
Finding 28 (P3, fast Xe polling could keep the iGPU awake during autosuspend timer slack) is fixed and verified in htop `1c205705` (installed in 3.5.3-18).
Findings 29–31 are fixed and verified in htop `1c205705` (installed in 3.5.3-18). They cover the GPU% process reader, forced-on Xe power policy, and detection of hardware reads during cached refreshes. Findings 28–31 independently re-verified live on xe by Claude Code.
Finding 32 (P3, `stat()` through `/proc/<pid>/fd/N` reaches each descriptor's own filesystem, so a hung network or FUSE mount could block htop; in the Intel sampler since the start, and now in the GPU% path) is fixed and verified in htop `1c205705` (installed in 3.5.3-18, Claude Code).
Findings 33–34 (alternate DRM node paths and optional syscall support) are fixed and verified in htop `1c205705` (installed in 3.5.3-18, Claude Code).
The original 33–34 reproductions also pass independently. Findings 35–38 from the follow-up audit are fixed and verified in htop `1c205705` (installed in 3.5.3-18, Claude Code).
Independent retesting confirmed fixes 35–38. Findings 39–41 are fixed and verified in htop `1c205705` (installed in 3.5.3-18, Claude Code).
P2 means normal priority; P3 means low priority.

## 2026-11-19, Claude Code (Claude Opus 5.5) — fixes for findings 39–41

The user asked me to go straight to fixing findings I verify. Fixed in the uncommitted working tree over htop `c3a0d73c`, still booted on xe.

Kernel check first. A subagent read `fs/proc/fd.c`, `fs/fuse/file.c`, `fs/nfs/file.c`, `fs/smb/client/cifsfs.c` and `fs/locks.c` at gregkh v7.3.4. `seq_show()` (fdinfo) prints `pos`, `flags`, `mnt_id` and `ino` from in-memory fields, lists locks with `show_fd_locks()` (in-memory lock lists), and calls `f_op->show_fdinfo` only if defined. None of the FUSE, NFS or SMB file operations define it. Parts of the FUSE, SMB and locks files came from a summary, not verbatim text. So reading fdinfo does not reach the file's filesystem.

`linux/IntelGPU.c`:

- 39: `IntelGPU_fdDevice()` now returns `IntelGPUFdKind`: other, denied, device, or unclassified. A path that is neither under `/dev/dri/` nor on a resolvable local mount is unclassified and never looked up, and neither is an over-long link text. `IntelGPU_readClients()` reads the fdinfo of unclassified descriptors, and `IntelGPU_parse(…, unclassified)` treats a record without `drm-` keys as not a client. A record with DRM keys goes through the driver/PCI filter and the finding 23 rules as before. An unreadable unclassified fdinfo only blocks a known client (`IntelGPU_blockClient()`) and does not mark the whole scan incomplete. A client under an alternate name on `overlay`, below a visible FUSE mount, or with no mount table, is now counted. `IntelGPU_isXeFd()` treats unclassified descriptors as not xe, so GPU% keeps upstream behavior for them, because reading their fdinfo is the wake the filter avoids. `IntelGPU_drmFile()` was replaced by `IntelGPU_ownNode()`.
- 40: the visible root mount index is computed once per parse (`mountRoot`), and `IntelGPU_localPath()` first collects the candidate mounts whose mount point is the path or one of its leading directories (one pass, stored lengths). `IntelGPU_childAt()` only scans those candidates. Resolver-only benchmark, `-O2`, median of three runs of 1,000 lookups of a 7-component local path: before 1.07 / 5.64 / 21.82 ms and after 0.25 / 1.22 / 4.25 ms, for 100 / 500 / 2,000 mounts. That matches Codex's numbers for the pre-35 resolver.
- 41: the harness's `__wrap_syscall` uses `SYS_statx` only when it is defined and aborts on any other call. A copy of the old wrapper failed to compile on a `config.h` shim that undefines `SYS_statx` ("`SYS_statx` undeclared").

`tools/test-intel-gpu.py`:

- The stacked-mount scenarios now use a locked stand-in next to the alias to show whether the path is looked up (`denied` 1) or identified by fdinfo (`denied` 0). Visible FUSE: not looked up, client counted, 20%. Hidden FUSE under a covering ext4: looked up, client counted, 20%.
- New: an alternate name on `overlay` is counted (1 MiB, 20%). A known client keeps counting while `mountinfo` is missing (30%, `incomplete=false`) and keeps its history when it returns (10%).
- Third fallback variant, "headers without SYS_statx".
- Negative controls: "fdinfo identity for unclassified paths" is new, and "alternate DRM names" was updated.

Checks:

- Build: no warnings. STYLE OK, `test-check-style.sh` ALL PASSED, `git diff --check` clean in both repos.
- `test-intel-gpu.py --mutations` with the live part on xe: 323 ok, ALL PASSED, all seven negative controls caught, all three fallback variants link and pass, shared parse holds. Live peaks: encode 32.2%, decode 31.3%, graphics 100%. `test-sampler.py`: 198 ok, ALL PASSED.
- End to end, the real htop from the working tree with the user's layout plus GPU% at `delay=1`, alternating 20 s windows: no htop 20.3% and 20.9% awake, htop 28.0% and 25.2%. The Intel heading was shown, and the user's config hash was unchanged.

Findings 39–41 are resolved.

Limits:

- A really hung network mount was not reproduced; the claim that fdinfo is safe rests on the kernel source read above.
- In GPU%, an xe node under an unclassifiable name (such as `overlay`) is still read by upstream's reader, which can wake the iGPU: power only, and rare.
- Unclassified descriptors (files on `/proc`, `/sys`, overlay, network and FUSE mounts) now cost one fdinfo read each per Intel scan.

Notes: still uncommitted and not packaged, together with findings 25–38. It needs a new htop commit after `c3a0d73c`, patch 0017 and pkgrel 18.

## 2026-11-19, Claude Code (Claude Opus 5.5) — confirmation of findings 39–41

I checked each against my finding 35–38 code and agree with all three:

- 39: `IntelGPU_fdDevice()` returns false for a path it cannot classify (no readable mount table, or a type outside the allowlist such as `overlay`) without signalling "unknown". `IntelGPU_readClients()` then treats a known client's descriptor as gone, and only `denied` blocks a client (`IntelGPU_blockClient()`).
- 40: `IntelGPU_localPath()` calls `IntelGPU_childAt()` for every path component, and each call scans the whole table.
- 41: `tools/intel-gpu-sample.c` uses `SYS_statx` unguarded under `INTELGPU_NO_STATX`.

Proposed fixes:

- 39: give the Intel sampler a third outcome, "unclassified", for a path it cannot classify. It then identifies the descriptor from its fdinfo instead of a target lookup. fdinfo is built from the kernel's open-file bookkeeping; I believe NFS, SMB and FUSE define no `show_fdinfo`, to be confirmed in the 7.3 source before relying on it. The parse treats a record with no `drm-` keys as not a client, and a record with DRM keys as before (driver/PCI filter, finding 23 semantics). A client under an alternate name on `overlay`, or with no mount table, is then counted rather than dropped. Codex's simpler alternative, blocking only known clients, would still miss a descriptor that was never classifiable. The GPU% xe filter keeps upstream behavior for unclassified paths, because reading xe fdinfo is the wake it avoids: a possible extra wake in a rare setup, no wrong data.
- 40: per lookup, first collect the mounts whose mount point is a leading component prefix of the path (one pass), then resolve parentage among those candidates only.
- 41: guard the harness wrapper's `SYS_statx` use, and keep `abort()` for any other system call.

## 2026-11-19, Codex — audit of Claude's fixes for findings 35–38

Audited the uncommitted working tree over htop `c3a0d73c`. The existing reproductions now pass. The sampler links without the libc statx symbol and keeps working after ENOSYS. A separate combined-reader harness returned EPERM on the first raw statx call, rejected a second call, and completed three scans. Visible and covered FUSE fixtures classified as expected, and the BeeGFS fixture was skipped. The original combined-reader trace now shows three opens of mountinfo in three shared refreshes.

### 39 (P2) — unknown mount information makes a known busy client look idle

When mountinfo cannot be loaded, the nonstandard path is rejected at `linux/IntelGPU.c:792` without setting `denied`. The scanner treats that result as a disappeared descriptor and removes its accounting history. In a stateful fixture the same GPU descriptor reported 20% usage and 1 MiB, then zero clients, 0% usage and zero bytes with `incomplete=false` during one refresh without a mount table. After restoration the next refresh had no usage rate while the baseline rebuilt. A separate fixture classified the same alternate device as ext4, overlay, and tmpfs. Both recognized local types reported 20% and 1 MiB. The overlay classification reported the same false idle values as the missing-table case. Preserve incomplete coverage for known clients when the mount check cannot classify the descriptor. These cases used simulated procfs and mount tables.

### 40 (P3) — the mount resolver scans the entire table at every path component

`IntelGPU_localPath()` calls `IntelGPU_childAt()` for each component of every candidate path. Each call scans all mounts even when no mountpoint could match. In a resolver-only benchmark of ordinary local paths, medians for 1,000 lookups were 1.17 ms with 100 synthetic mounts, 4.99 ms with 500 mounts, and 20.63 ms with 2,000 mounts. The previous resolver took 0.22, 0.93, and 4.30 ms respectively. The comparison used optimized builds and three runs per size. It measures mount resolution without descriptor I/O or terminal rendering. Indexing the parsed table by parent ID and mountpoint would preserve the parentage result and avoid repeated full scans.

### 41 (P3) — the fallback test requires the syscall number it simulates as missing

`tools/intel-gpu-sample.c:23` uses `SYS_statx` without a feature guard whenever `INTELGPU_NO_STATX` is defined. With that one macro removed in a temporary header shim, the production sampler built and reported 20% for the fixture while the fallback test variant failed to compile. Guard the injection harness as well as the production call so the suite can exercise the path-only build on those headers.

The htop rebuild completed without warnings. Style and all seven checker self-tests passed. The Intel suite passed 309 checks, including live Xe workloads and six mutation controls. The AMD suite passed 198 checks. On the active Xe desktop with a 1,000 ms autosuspend delay, one 15-second window per layout at a 0.1 s refresh gave 30.0% awake with neither feature, 29.1% with GPU% only, 25.2% with Intel headers only, and 33.2% with both. No persistent wake was observed. No hung filesystems were tested. Installed package is 3.5.3-17. This turn edited only audit records.

## 2026-11-19, Claude Code (Claude Opus 5.5) — fixes for findings 35–38

Fixed at the user's request, in the uncommitted working tree over htop `c3a0d73c`, still booted on xe.

`linux/IntelGPU.c`:

- 35: `IntelGPU_lookupDevice()` now calls `statx` through `syscall(SYS_statx, …)` when `SYS_statx`, `STATX_TYPE` and `AT_STATX_DONT_SYNC` are defined, so no libc `statx()` symbol is needed. On `ENOSYS` or `EPERM` it remembers that `statx` is missing and uses `fstatat()` (or `stat()` without it) from then on, instead of dropping the client. Added `<sys/syscall.h>`.
- 36: the mount table now keeps mount and parent IDs. `IntelGPU_localPath()` resolves a path the way a path walk does. It starts at the root mount (the `/` entry whose parent is not in the table), follows mounts stacked on the same place to the visible one (`IntelGPU_topmost()`), and at each leading directory enters the last child of the current mount at that point (`IntelGPU_childAt()`). Mounts hidden under a later mount are never reached. An unreadable or unresolvable table counts as not local.
- 37: `IntelGPU_localType()` is an allowlist (`devtmpfs`, `tmpfs`, `ramfs`, `ext2/3/4`, `xfs`, `btrfs`, `f2fs`, `bcachefs`, `zfs`, `jfs`, `nilfs2`, `vfat`, `exfat`, `ntfs3`). Every other type, including unlisted network filesystems and `proc`/`sysfs`, is skipped.
- 38: `IntelGPU_loadMounts(monotonicMs)` parses once per refresh timestamp, and the Intel meters and the GPU% filter share it. `IntelGPU_fdDevice()` and `IntelGPU_drmFile()` take `monotonicMs`, and the two `mountsLoaded = false` resets are gone.
- Live classification on this desktop: `/`, `/home`, `/mnt/storage1`, `/mnt/games0`, `/run/user/1000`, `/tmp` and `/dev/dri` are local. The FUSE document portal `/run/user/1000/doc`, `/proc` and `/sys` are skipped. A second lookup in the same refresh reused the parse.

Tests:

- `tools/intel-gpu-sample.c`: with `-DINTELGPU_NO_STATX -Wl,--wrap=syscall` it answers `SYS_statx` with `ENOSYS` and aborts on a second attempt in the same process.
- `tools/process-gpu-sample.c`: with a second argument `intel`, it runs `IntelGPU_getSample()` in the same refresh before `GPU_readProcessData()`, as htop does. It counts `/self/mountinfo` opens per refresh through `--wrap=fopen` and reports them as `mountinfo`.
- `tools/test-intel-gpu.py`:
  - Fake mount rows now carry IDs and parents (`Tree.mount(path, fstype, parent)`).
  - New scenarios: an unlisted network filesystem (`beegfs`) is skipped; an alternate name below a visible FUSE mount is skipped; the same path below a FUSE mount hidden by a covering ext4 mount is found (one client, 1 MiB, 20% usage).
  - `fallback_build_test()` now runs two variants and reports a harness crash as a failure. "statx rejected at runtime" uses the normal config, `NO_STATX` and `--wrap=statx`. "no openat, readlinkat, fstatat or statx" adds the shim `config.h` and `--wrap=readlinkat --wrap=fstatat`.
  - New `mount_table_test()` expects exactly one mount table open per refresh with both readers running.
  - Process-column checks ignore the new `mountinfo` key.
  - Negative controls: "local filesystem allowlist" and "stacked mounts" are new; "alternate DRM names" was updated; "network and FUSE skip" was replaced.

Checks:

- Build: no warnings. STYLE OK, `test-check-style.sh` ALL PASSED, `git diff --check` clean in both repos.
- `test-intel-gpu.py --mutations` with the live part on xe: 309 ok, ALL PASSED, all six negative controls caught, both fallback variants link and pass, shared parse confirmed. Live peaks: encode 32.1%, decode 17.9%, graphics 100%. `test-sampler.py`: 198 ok, ALL PASSED.
- Proof runs on mutated copies (the real file untouched): removing the ENOSYS fallback failed both fallback variants (dropped client, then the abort); keeping the fallback but retrying `statx` failed both on the abort; removing the per-refresh cache gave `[2, 2, 2]` opens and failed the shared-table check. The unmodified source passed all of them.
- End to end with the real htop from the working tree, the user's layout plus GPU% at `delay=1`, alternating 20 s windows: no htop 23.1% and 23.0% awake, htop 25.7% and 26.8%. The Intel heading was shown.

Findings 35–38 are resolved.

Limits:

- A really hung network mount was not reproduced.
- Paths from another mount namespace are still resolved against htop's own table. Their lookup keeps `AT_STATX_DONT_SYNC`, which is weaker on SMB, and falls back to plain `stat` where `statx` is missing.
- Mount-ID resolution was tested with fake tables, plus a live classification of this desktop's real table.

Notes: still uncommitted and not packaged, together with findings 25–34. It needs a new htop commit after `c3a0d73c`, patch 0017 and pkgrel 18.

## 2026-11-19, Claude Code (Claude Opus 5.5) — confirmation of findings 35–38

I checked each against my finding 33–34 code and agree with all four:

- 35: `IntelGPU_lookupDevice()` selects `statx()` on `#ifdef STATX_TYPE`. That macro comes from the kernel headers (`<linux/stat.h>`, included explicitly), so an older libc without `statx()` fails to link. A runtime `ENOSYS` (an old kernel, or a seccomp profile) makes the lookup return false, which silently drops every client: a false zero marked complete.
- 36: `IntelGPU_localPath()` chooses the longest mount-point string and ignores mount IDs and parents, so a hidden child mount can claim a visible path.
- 37: `IntelGPU_remoteType()` is a denylist, so unlisted network filesystems (BeeGFS, as Codex notes) count as local.
- 38: `mountsLoaded` is cleared both in `IntelGPU_readClients()` and on each new `monotonicMs` in `IntelGPU_isXeFd()`, so one refresh can parse mountinfo twice.

Proposed fixes:

- 35: use the raw `SYS_statx` system call (no libc symbol). On `ENOSYS`/`EPERM`, fall back to `fstatat()`/`stat()` and remember that `statx` is unavailable. Simulate that in the fallback-build test.
- 36: resolve the path by walking mount parentage from the root mount, following stacked mounts and descending into the topmost child mounted at each path prefix. An unresolvable table counts as unknown and is skipped.
- 37: switch to an allowlist of local types (`devtmpfs`, `tmpfs`, `ramfs`, `ext2/3/4`, `xfs`, `btrfs`, `f2fs`, `bcachefs`, `zfs`, `jfs`, `nilfs2`, `vfat`, `exfat`, `ntfs3`). Container `/dev` directories are `tmpfs`, so finding 33 stays fixed.
- 38: key the parsed table to the refresh `monotonicMs`, so both readers share one parse.

## 2026-11-19, Codex — audit of Claude's fixes for findings 33–34

Retested the uncommitted working tree over htop `c3a0d73c`. Finding 33's original reproduction now reports one client, 20% usage and 1 MiB for both the usual render-node name and an alternate local name using the production prefix. An inotify watch confirmed the generic GPU reader skipped the Xe fdinfo under both names. For finding 34, a separate build disabled openat, fstatat and readlinkat and made the latter two symbols unavailable to the linker. All five mixed-device process-reader checks passed, including the alternate-name Xe FIFO, AMD counters and rebinding.

### 35 (P2) — unavailable statx silently drops every GPU client

At `linux/IntelGPU.c:682`, the kernel header's `STATX_TYPE` macro selects a direct libc call. It does not establish that libc provides the symbol or that the call works at runtime. With working statx the fixture reported one client, 20% usage and 1 MiB. When the API returned ENOSYS, the same input produced zero clients, 0% usage and zero bytes with `incomplete=false`. With current headers but the statx symbol unavailable at link time, the sampler did not link. Both cases were simulated on the current toolchain. The new no-*at test still uses statx on this host. Probe the function at build time and exercise an unavailable-at-runtime case, retaining mount eligibility checks before using the supported fallback.

### 36 (P3) — a hidden child mount can hide a visible local GPU from the meters

`IntelGPU_localPath()` selects the longest mountpoint string across all rows. It discards the mount and parent IDs. In a fixture a second local mount covered a parent directory that had a FUSE child on the lower mount. The visible local GPU was below the child's old pathname. Without the hidden child row the sampler reported 20% usage and 1 MiB. Adding that row alone produced zero clients, usage and memory with complete coverage reported. Consider parentage and mount visibility when resolving stacked mounts. This was a simulated mount table in a single namespace. [Linux mountinfo semantics](https://man7.org/linux/man-pages/man5/proc_pid_mountinfo.5.html)

### 37 (P3) — unrecognized network filesystems are classified as local

The default return in `IntelGPU_remoteType()` marks every unlisted filesystem as local. An isolated classifier check returned local for ext4 and BeeGFS and remote for fuse.sshfs. BeeGFS is a network filesystem with metadata servers, so this permits the target attribute lookup that finding 32 intended to skip. Treat unknown filesystem types conservatively when admitting alternate paths. This was a classification test only. No BeeGFS installation, server contact or actual stall was tested. [BeeGFS architecture](https://doc.beegfs.io/latest/architecture/overview.html)

### 38 (P3) — both readers can reload mountinfo in one refresh

The Intel client scan and the generic Xe process scan each independently clear `mountsLoaded`. A trace of three shared timestamps with both real reader functions scanning and the device active showed six opens of mountinfo. Each load also frees and recreates the mountpoint strings. Key the shared table to the refresh timestamp so both consumers reuse one parse. The trace measured duplicate work, not a desktop CPU slowdown.

The development binary rebuilt without warnings. Style and all seven checker self-tests passed. The Intel suite passed 296 checks, including live Xe workloads and five mutation controls. The AMD suite passed 198 checks. At a 0.1 s refresh on the live Xe desktop, one 15 s window per layout gave 28.2% awake with neither feature, 38.9% with GPU% only, 33.0% with Intel headers only and 34.9% with both. No continuous wake was observed. Installed package is 3.5.3-17. Only audit records were edited.

## 2026-11-19, Claude Code (Claude Opus 5.5) — fixes for findings 33 and 34

Fixed at the user's request, in the uncommitted working tree over htop `c3a0d73c`, still booted on xe. This replaces my finding 32 helper `IntelGPU_drmLinkStat()`.

Kernel check first. A subagent read `fs/fuse/dir.c`, `fs/nfs/inode.c` and `fs/smb/client/inode.c` at gregkh v7.3.4. `statx(AT_STATX_DONT_SYNC)` with only `STATX_TYPE` skips server or daemon traffic in `fuse_getattr()` and `nfs_getattr()`. `cifs_getattr()` still revalidates when the inode's cached `time` is 0. Path-walk revalidation is outside those functions. So `DONT_SYNC` alone cannot guarantee a hung mount is never queried, and the fix does not rely on it.

`linux/IntelGPU.c`, new `IntelGPU_fdDevice()`. Every step but the last avoids the target filesystem:

1. `readlinkat()` the `/proc` fd link, or `readlink()` on the path in builds without it.
2. Link texts that are not absolute paths (`socket:[…]`, `pipe:[…]`, `anon_inode:…`) are never devices and are skipped.
3. Paths under `INTELGPU_DRM_PREFIX` (`/dev/dri/`) are looked up directly.
4. Any other path is matched against htop's own mount table (`/proc/self/mountinfo`, parsed lazily once per refresh, octal escapes decoded, longest and latest mount point wins). It is skipped when that filesystem is network or FUSE (`nfs*`, `cifs`, `smb3`, `smbfs`, `9p`, `ceph`, `afs`, `coda`, `lustre`, `glusterfs`, `virtiofs`, `orangefs`, `ncpfs`, `fuse*`) or when the table cannot be read. Otherwise it is looked up, so a DRM node under another name (for example `docker --device host:other-path`) is found by its device number again (33). On this desktop, `/`, `/home`, `/tmp`, `/mnt/storage1` and `/dev/dri` classify as local and the document portal `/run/user/1000/doc` (FUSE) as remote.
5. The lookup uses `statx(..., AT_STATX_DONT_SYNC, STATX_TYPE)` when available, as an extra guard for paths from other mount namespaces. Otherwise it uses `fstatat()`, or `stat()` in builds without it. The device number comes from the result.

Builds without `readlinkat`/`fstatat`/`openat` reach a directory-relative link through `/proc/self/fd/<dir>/<name>` (34). `IntelGPU_drmFile()` and `IntelGPU_isXeFd()` both use the helper and now carry a `dev_t`. Added `<linux/stat.h>` (IWYU, `statx`).

`tools/test-intel-gpu.py`:

- Every fake tree gets `proc/self/mountinfo` (root ext4), and `Tree.mount()` adds entries.
- The hung-mount stand-in is now a `fuse.sshfs` mount (skipped, `denied` 0). The same locked path on ext4 is looked up (`denied` 1).
- New "DRM node under an alternate name" scenario: one client, 1 MiB, 20% usage.
- The process-column fixture adds an alternate-name xe node whose fdinfo is a FIFO, and it must be skipped.
- New `fallback_build_test()` compiles with a shim `config.h` that undefines `HAVE_OPENAT`, `HAVE_READLINKAT` and `HAVE_FSTATAT`, and links with `--wrap=readlinkat --wrap=fstatat` without wrappers, so any direct use fails to link. It then runs the full fixture suite. A one-line probe confirmed the wrap trick fails on a direct `readlinkat()` call.
- Negative controls: "network and FUSE skip" and "alternate DRM names" replace "DRM link filter".

Checks:

- Build: no warnings. STYLE OK, `test-check-style.sh` ALL PASSED, `git diff --check` clean in both repos.
- `test-intel-gpu.py --mutations` with the live part on xe: 296 ok, ALL PASSED, all five negative controls caught, fallback build links and passes. Live peaks: encode 32.5%, decode 32.5%, graphics 100%. `test-sampler.py`: 198 ok, ALL PASSED.
- End to end, the real htop from the working tree with the user's layout plus GPU% at `delay=1`, alternating 20 s windows: no htop 22.0% and 22.4% awake, htop 24.2% and 27.5%. The Intel heading was shown in both runs.

Findings 33 and 34 are resolved.

Limits:

- A really hung NFS, SMB or FUSE mount was not reproduced.
- A path from another mount namespace whose prefix looks local in htop's namespace is still looked up, guarded only by `AT_STATX_DONT_SYNC`, which is weaker on SMB per the kernel check.
- The process-column reader was not re-run in a no-`openat` build; the Intel sampler compiled it there, but did not execute that branch.

Notes: still uncommitted and not packaged, together with findings 25–32. It needs a new htop commit after `c3a0d73c`, patch 0017 and pkgrel 18.

## 2026-11-19, Claude Code (Claude Opus 5.5) — confirmation of findings 33 and 34

I reviewed both against my finding 32 code and agree with both.

- 34: `IntelGPU_drmLinkStat()` calls `readlinkat()` and `fstatat()` directly. `linux/Compat.h` provides `Compat_readlinkat()` and `Compat_fstatat()` with path-based fallbacks for builds without `HAVE_READLINKAT` / `HAVE_FSTATAT` / `HAVE_OPENAT`. This build defines all three, so it is unaffected, but the fallback configuration cannot link.
- 33: the prefix test runs before the device-number test, so a DRM node that procfs reports outside `/dev/dri/` (a container `--device host:other-path` mapping) is rejected without a device check. That is a silent client loss in the Intel sampler, and a missed xe skip in the GPU% path. The checks were my own design; the test fixtures only used `/dev/`-prefixed targets, so they could not catch it.

Proposed fix direction, not implemented yet:

- Skip link texts that are not absolute paths (`socket:[…]`, `pipe:[…]`, `anon_inode:…`); they can never be device nodes.
- Keep the `/dev/dri/` fast path.
- For other absolute paths, get the type and device number with `statx(..., AT_STATX_DONT_SYNC | AT_NO_AUTOMOUNT, STATX_TYPE, …)`, which asks network and FUSE filesystems for cached attributes instead of a server round trip. Before relying on that, check against the 7.3 kernel source that FUSE, NFS and SMB honor `AT_STATX_DONT_SYNC` on this path. Where `statx` is unavailable, fall back to the current prefix-only behavior.
- Route all calls through the Compat layer (34), and add fixtures for an alternate-name DRM link on both i915 and xe.

## 2026-11-19, Codex — audit of Claude's finding 32 fix

Compared the uncommitted change over htop `c3a0d73c` with a saved copy of the pre-32 sampler containing fixes 25–31. Tracing both readers on a fixture with an unrelated ordinary file showed a single readlinkat on its descriptor and no target stat. This confirms the intended lookup behavior for stable descriptors. A stalled remote filesystem was not exercised. Claude's previously documented descriptor-reuse race remains a limit.

### 33 (P2) — an alternate DRM node path silently drops a client and bypasses the Xe process filter

The prefix check at `linux/IntelGPU.c:579` rejects a descriptor before checking its character-device number. Two fixture proc links reported different names for the same Intel render device: the standard node and a path outside `/dev/dri/`. The comparison binaries used the production prefix. With a simulated i915 client, the pre-32 sampler reported one client, 20% usage and 1 MiB under both names. The reviewed version gave the same result for the standard name, but returned zero clients, 0% usage and zero bytes with `incomplete=false` for the alternate name. On the Xe fixture an inotify watch also observed the generic GPU reader opening the alternate descriptor's fdinfo. Before the change it skipped both names.

This affects paths as reported by procfs, such as when a device is exposed under another name. On the live host, opening the ordinary PCI by-path alias produced `/dev/dri/renderD129` in procfs and passed the filter. The alternate-path result is a fixture comparison, not a live container or power measurement. Add coverage for an alternate reported name and retain device-identity checks without restoring arbitrary target lookups. [Example of custom device paths](https://docs.docker.com/reference/cli/docker/container/run/#add-host-device-to-container---device)

### 34 (P3) — the optional-system-call fallback now requires readlinkat and fstatat

`IntelGPU_drmLinkStat()` calls both APIs directly, including when its caller passes an absolute path in the no-openat branch. Configure probes these functions separately and the project's Compat layer provides fallbacks. A scratch build with all three feature flags disabled and both symbols unavailable at link time linked the pre-32 sampler. The reviewed version failed on the two new references. Use the available path-based or compatibility calls in this configuration and exercise the link without the optional symbols. The normal CachyOS build has both functions.

The Intel module rebuilt and htop relinked without warnings. Style and all seven checker self-tests passed. The Intel suite passed 287 checks, including live Xe workloads and the four mutation controls. The AMD suite passed 198 checks. On the standard device layout at 0.1 s refresh, the iGPU was awake for 32.3% with neither feature, 21.5% with GPU% only, 31.7% with Intel headers only and 36.2% with both (one 15 s window each on the active desktop). No regression to continuous wake was observed there. Installed version is 3.5.3-17. The audit added records only.

## 2026-11-19, Claude Code (Claude Opus 5.5) — fix for finding 32

Fixed at the user's request, in the uncommitted working tree over htop `c3a0d73c`, still booted on xe.

- `linux/IntelGPU.c`: new `IntelGPU_drmLinkStat()`. It `readlinkat()`s the `/proc/<pid>/fd/N` link first, which reports the target path without touching the target filesystem. It only follows the link with `fstatat()` when the path starts with `INTELGPU_DRM_PREFIX` (default `/dev/dri/`), and then requires a character device. `IntelGPU_drmFile()` (Intel header sampler, `AT_FDCWD` plus the full path) and `IntelGPU_isXeFd()` (GPU% path, the process directory fd, or `AT_FDCWD` in builds without `openat`) both use it. Permission errors from either call still count as denied, as before. Added `<unistd.h>`.
- `tools/test-intel-gpu.py`: fake builds pass `-DINTELGPU_DRM_PREFIX="/dev/"`, because fixture links point at `/dev/null` and `/dev/zero`. Live builds keep `/dev/dri/`. New stateful scenario "descriptor on another filesystem is never followed": next to a real client, a descriptor's link points into a `chmod 0` directory that stands in for a hung mount. The scenario expects `denied` 0, complete readings and 20% usage. New negative control "DRM link filter" disables the prefix check.

Checks:

- Build: no warnings. STYLE OK (IWYU accepts `<unistd.h>`). `test-check-style.sh` ALL PASSED. `git diff --check` is clean in both repos.
- `test-intel-gpu.py --mutations` with the live part on xe: 287 ok, ALL PASSED, all four negative controls caught. Live peaks: encode 32.1%, decode 31.4%, graphics 100%, so the real `/dev/dri/` filter still finds the iGPU's clients. The process-column fixture (Xe FIFO skipped, AMD counted) passes. `test-sampler.py`: 198 ok, ALL PASSED.
- Mutation check run separately: with the prefix check disabled, exactly the two new checks fail, with `denied` 1, because the old behavior followed the link. Everything else passes.

Finding 32 is resolved. Limits: a really hung NFS or FUSE mount was not reproduced. The locked directory proves the link is no longer followed, which is what prevents the block. There is a tiny race: a descriptor closed and reused between `readlinkat()` and `fstatat()` could still be followed once. i915 was not re-run live in this boot.

Notes: still uncommitted and not packaged, together with findings 25–31. It needs a new htop commit after `c3a0d73c`, patch 0017 and pkgrel 18.

## 2026-11-19, Claude Code (Claude Opus 5.5) — live xe verification of findings 28–31

Still booted on xe. Audited Codex's uncommitted changes over htop `c3a0d73c`:

- `IntelGPU.c`: the read spacing is now delay + delay/4 + 50 ms (28), and is skipped when `power/control` is `on` (30). New `IntelGPU_isXeFd()`.
- `IntelGPU.h`.
- `linux/GPU.c` (upstream): an include, a `continue` hook before each fdinfo read, and the non-`openat` fdinfo path built from `procFd` instead of `PROCDIR`/pid.
- `tools/process-gpu-sample.c` (new), `tools/intel-gpu-sample.c`, `tools/test-intel-gpu.py`, `tools/check-style.sh`, and the docs.

Review:

- 28: matches the variant I measured in the previous section.
- 29: upstream's process reader only uses `drm-engine-*` values in nanoseconds (`linux/GPU.c` lines 173–187). xe reports `drm-cycles-*`, so skipping xe descriptors loses no data while avoiding the runtime-PM wake. The upstream diff is 6 lines added and 2 changed. The non-`openat` path change is not needed on Linux/glibc builds (`HAVE_OPENAT` is set), but lets the new fixture run in a no-`openat` build.
- 30 and 31: the forced-on bypass and the FIFO-guarded cached refresh are sound and covered.

Checks:

- Build: no warnings. STYLE OK. `test-check-style.sh` ALL PASSED. `git diff --check` is clean in both repos.
- `test-intel-gpu.py --mutations` with the live part on xe: 282 ok, ALL PASSED. `test-sampler.py`: 198 ok, ALL PASSED.
- End-to-end power check with the real htop: the user's layout plus `GPU_PERCENT` in the Main screen, `delay=1` (0.1 s), alternating 25 s windows run through `htop-capture.py`, with copies of the user's config (hash unchanged afterwards):

| htop | iGPU awake |
|---|---|
| none | 17.9%, 18.6%, 21.4% |
| installed 3.5.3-17 (`c3a0d73c`) | 99.9%, 99.9% |
| working tree | 25.7%, 31.4% |

Findings 28–31 are confirmed resolved. The working tree leaves about 5–12 points above baseline at htop's fastest refresh.

### 32 (P3) — `stat()` through `/proc/<pid>/fd/N` reaches each descriptor's own filesystem

`IntelGPU_drmFile()` (`stat(path)`) and the new `IntelGPU_isXeFd()` (`fstatat(procFd, "fd/N", &st, 0)`) follow the `/proc` magic link, so the kernel asks the target's filesystem for attributes. For a file on an NFS, SMB or FUSE mount whose server or daemon has stopped responding, that call can block. This is the well-known reason `lsof` can hang (and why it has `-b`). The Intel sampler has done this for every descriptor of every readable process since `bb4f7331`, whenever an Intel meter is shown. The finding 29 fix adds it to upstream's GPU%/GPU_TIME path, which upstream itself never does: upstream only reads `fdinfo`. Not reproduced with a hung mount here; reasoning only. Suggested fix: `readlinkat()` the descriptor first (it reports the path without touching the target filesystem), and only `stat()` targets that start with `/dev/dri/`. Sockets, pipes, anonymous inodes and regular files are then skipped without any filesystem call. Add a fixture with a non-DRM descriptor whose target would block if stat'ed (for example a FIFO reached through a symlink in the fake proc tree), to show it is never followed.

Notes: everything is still uncommitted and not packaged. It needs a new htop commit after `c3a0d73c`, patch 0017 and pkgrel 18.

Limits: one machine, one xe boot. 25 s windows on a live desktop are noisy.

## 2026-11-19, Codex — fixes for findings 29–31

**29.** The generic reader used by GPU%, GPU_TIME and the stock GPU meter now checks the descriptor's character device and current sysfs driver binding before opening fdinfo. It skips Xe descriptors, whose cycle counters this nanosecond-based reader cannot use. Other descriptors, including those whose driver cannot be identified, still go through the original accounting path. The selected Intel iGPU's header meters continue sampling Xe cycles. [Xe fdinfo interface](https://github.com/gregkh/linux/blob/v7.3.4/drivers/gpu/drm/xe/xe_drm_client.c#L21-L71)

Full htop was tested at 0.1 s refresh on the 270K Plus with Xe, automatic runtime PM, and a 1000 ms delay. Each window began with a single open and close of the Intel render node. Percentages come from the change in runtime_active_time divided by elapsed wall time. The isolated layouts used 18 s windows. The project preview layout with GPU% added and its no-htop controls used approximately 22 s windows.

| Layout | Awake time |
|---|---|
| Intel header meters only | 22.6% |
| GPU% column only | 26.8%, 24.0% |
| Intel headers and GPU% only | 20.4%, 28.5% |
| Neither (clock header only) | 18.6% |
| Project preview with GPU% | 35.0%, 30.0% |
| No htop | 32.0%, 31.8% |

The original project-layout runs were 100% awake. After anchoring the descriptor lookup to htop's open process directory, a final 18 s comparison measured 18.8% without htop, 17.6% with GPU% alone and 22.0% with the full project layout and GPU%. These are short windows on one running desktop.

A mixed-driver fixture exercises the actual process-column reader. Reading Xe fdinfo would block on a FIFO. The reader skipped it, counted AMD engine time, recovered when the same device number changed driver, and kept counting when driver metadata was missing. The same checks passed in a scratch build configured without openat. Removing the filter made the test time out at the Xe FIFO. During simultaneous Intel and AMD hardware encodes, the sanitized full display showed Intel video at 32% and the AMD process at 37.3% GPU with 1.63303 s GPU_TIME.

**30.** An explicit `power/control=on` permits fresh Intel header readings on every active refresh. Returning to `auto` applies the configured interval from the last completed read. A single-process fixture tests both transitions. Removing the policy check failed the fixture. This case was simulated so the live machine could keep its normal power policy.

**31.** The Xe interval fixture replaces both the clock and client fdinfo with blocking FIFOs at elapsed 1299 ms. It restores regular files and checks fresh clock and counter values at 1300 ms. Two scratch builds independently reintroduced a clock scan or a client scan during a cached refresh. Each timed out at the guarded refresh.

Validation on the working tree over htop `c3a0d73c`: build and style passed, including all seven style-checker self-tests. The Intel suite passed 282 checks including the process reader and live Xe workloads. The AMD suite passed 198 checks. The full display check produced no ASan or UBSan reports. The fixes are local and uncommitted. Installed package version is 3.5.3-17.

## 2026-11-19, Codex — self-audit of the finding 28 fix

Reviewed the uncommitted Xe timing change over htop `c3a0d73c` with project tools based on `934c2a6`. The 1300 ms interval for a 1000 ms autosuspend delay matches the Linux timer slack plus the existing 50 ms margin. The fixture suite rejected all three scratch timing variants (the earlier 50 ms margin, a constant 300 ms margin, and 50% proportional slack). The development build, style check, 271 Intel checks with live Xe workloads, and 198 AMD checks passed. [Linux 7.3.4 timer implementation](https://github.com/gregkh/linux/blob/v7.3.4/drivers/base/power/runtime.c#L581-L594)

### 29 (P2) — the GPU% process column can keep Xe awake independently of the Intel header meters

The previous power comparison measured a standalone sampler. It missed a second reader in the full program and therefore did not establish the power benefit for the project's GPU% layout. At 0.1 s refresh on the 270K Plus with Xe, automatic runtime PM and a 1000 ms delay, full htop with the project preview layout plus the GPU% process column kept the iGPU awake 100% in two 22 s windows on each of the before and after builds. The comparison build differed only in restoring the 50 ms constant. Without htop, both baseline windows measured 31.0%.

Independent 18 s windows used the fixed htop with minimal layouts. Each window started with one open and close of the Intel render node. The percentage is the change in `runtime_active_time` divided by wall time. Captured terminal output confirmed the requested rows and column were displayed.

| Enabled in htop | iGPU awake |
|---|---|
| Intel header meters only | 30.4%, 29.3% |
| GPU% process column only | 100%, 100% |
| Intel headers and GPU% | 100%, 100% |
| Neither (clock header only) | 25.1% |

The GPU% column enables upstream `GPU_readProcessData()` from `linux/LinuxProcessTable.c`. It reads process fdinfo outside the custom Intel sampler. The experiment isolates the column's effect on this desktop. It does not identify the particular client that triggers it. Scope the documented power result to the Intel header sampler and include this column in end-to-end power checks before claiming a benefit for that layout. The project plan asks to preserve upstream process-column behavior.

### 30 (P3) — forced-on Xe devices reuse stale readings

`IntelGPU_xeReadDue()` consults the delay even when `power/control` is `on`, which forbids runtime suspend. In a fixture with a 10000 ms delay, the clock changed from 800 to 1700 MHz after the initial sample. The current sampler still displayed 800 MHz at elapsed 12549 ms, then 1700 MHz at 12550 ms. The prior sampler already throttled in this configuration and refreshed at 10050 ms. Bypass the interval when the policy explicitly reports `on` and cover switching between `on` and `auto` in one process. This was reproduced with a fixture only. [Kernel power policy documentation](https://docs.kernel.org/power/runtime_pm.html)

### 31 (P3) — the Xe timing fixture can miss a hardware read during a cached refresh

In a scratch build, inserting `IntelGPU_readTopology()` immediately before restoring the cached sample made an extra clock read. Every existing Intel fixture assertion passed. A separate probe replaced the clock file with a FIFO after the initial sample. It observed zero reads at elapsed 1299 ms and a read at 1300 ms on the working tree, and detected the scratch build's extra read at 1299 ms. Include an observable read in the permanent cached-refresh test so that it detects this power regression even if the displayed values stay the same.

## 2026-11-19, Codex — verified fix for finding 28

Linux 7.3.4 allows the runtime autosuspend timer to expire up to 25% after the configured delay. With a 1000 ms delay, the previous Xe sampler could read the clock and counters again after 1050 ms, while the timer could still be pending. The corrected sampler allows the proportional slack plus the existing 50 ms margin after the previous read finishes, giving a 1300 ms interval on this machine. It continues to check sleep on every refresh. [Kernel timer implementation](https://github.com/gregkh/linux/blob/v7.3.4/drivers/base/power/runtime.c#L581-L594)

Measured on the 270K Plus running Xe on 7.3.4-1-cachyos. Each 30-second window started with one open and close of the Intel render node. GPU awake time came from the change in `power/runtime_active_time`. Both samplers polled every 0.1 s. The windows ran in the order baseline, original, fixed, fixed, original, baseline.

| Reader | First window awake | Second window awake |
|---|---:|---:|
| No sampler | 30.4% | 31.4% |
| Working tree before this fix | 38.4% | 65.2% |
| Fixed working tree | 35.9% | 35.9% |

The deterministic Xe fixture failed five timing checks before the fix. It now checks that a 1000 ms delay holds readings at 1050 and 1299 ms and refreshes them at 1300 ms. A 250 ms delay also exercises the proportional margin. Both timing boundaries pass, along with recovery on wake and nonpositive delays.

The build and style checks passed. The Intel suite passed 271 checks including mutation controls and live Xe encode, decode and graphics. The AMD suite passed 198 checks. At a 0.1 s refresh, sanitized htop showed 31% video during a live encode with no ASan or UBSan reports. Hardware measurements cover one Xe device on a running desktop, so background GPU activity contributes to the awake times. The fix is uncommitted over htop `c3a0d73c`. Installed package version is 3.5.3-17.

## 2026-11-19, Claude Code (Claude Opus 5.5) — live xe verification of the finding 27 fix

Still booted on xe. Audited Codex's uncommitted change over htop `c3a0d73c`. `IntelGPU_refresh()` now treats `resuming` as sleep, like `suspended` and `suspending` (matching AMD finding 17). Two fixture steps cover it: an xe step in the throttle scenario, and an i915 step whose clock file is a FIFO that would block if read while resuming.

- Build: no warnings. STYLE OK. `git diff --check` is clean in both repos.
- `test-intel-gpu.py --mutations` with the live part on xe: 270 ok, ALL PASSED, including "Xe resuming still shows sleep" and "resuming skips dynamic reads". Live peaks: encode 33.8%, decode 32.0%, graphics 100%. `test-sampler.py`: 198 ok, ALL PASSED.
- Live: a standalone sampler at a 0.1 s refresh for 60 s returned suspended 326 and active 268, with no `unavailable`. Before the fix, 1 of about 60 to 120 samples was `unavailable`.

Finding 27 is confirmed resolved.

### 28 (P3) — at a 0.1 s refresh the xe read spacing is shorter than the kernel's autosuspend slack

The finding 25 fix reads xe counters and clocks again `autosuspend_delay_ms` + 50 ms after the previous read finished. That holds the iGPU awake much less at 0.25 s and slower (26.7% and below, see the previous section). But htop's fastest delay is 0.1 s, and there the read lands while the kernel has not yet suspended the device. Linux runtime PM arms the autosuspend timer with slack of up to a quarter of the delay. So with xe's 1000 ms delay, suspend can come up to about 1250 ms after the last use, and a read at 1050–1150 ms re-arms it. Measured in alternating 30 s windows with a standalone sampler polled every 0.1 s:

| Sampler | iGPU awake |
|---|---|
| none (baseline, 4 windows) | 22.5–29.5% |
| working tree (delay + 50 ms) | 63.5%, 53.6%, 63.9%, 76.6% |
| scratch variant (delay + delay/4 + 50 ms) | 21.1%, 37.0% |

The slack explanation fits the variant's result, though I did not read the kernel source to confirm it. Suggested fix: space xe reads by `delay + delay / 4 + 50` ms, and update the fixture times in "Xe runtime PM sampling interval" to match. The cost is xe meters updating every about 1.3 s instead of every about 1.05 s at fast refreshes. htop's default 1.5 s refresh is unaffected either way.

Notes: still uncommitted and not packaged. It needs a new htop commit after `c3a0d73c`, patch 0017 and pkgrel 18.

Limits: one machine, one xe boot. 30 s windows are noisy because other processes (here ffmpeg-converter and Xwayland hold the iGPU) wake it too.

## 2026-11-19, Codex — verified fix for finding 27

On the working tree based on htop `c3a0d73c` with the fixes for 25–26 present, the new i915 and Xe fixture steps both returned `unavailable` during `resuming`. These were the only failures before the fix.

The Intel sampler now handles `resuming` in the existing sleep branch. On i915 the clock FIFO stayed unread through resume. On Xe the transition was visible even inside the autosuspend sampling interval. Both drivers took a fresh baseline on the first active refresh. With the Xe fixture held at `resuming`, a sanitized htop displayed `sleep` on the heading, usage, clock, memory and video rows.

The development build and style check passed. The Intel suite passed all 270 checks, including the three mutation controls and live Xe workloads. The AMD suite passed all 198 checks. Full-program fixture and live display checks produced no ASan or UBSan reports. The resume transition was forced only in fixtures. The fix is uncommitted and the installed package is 3.5.3-17.

## 2026-11-19, Claude Code (Claude Opus 5.5) — live xe verification of the finding 25 and 26 fixes

Still booted on xe (`i915.force_probe=!7d67 xe.force_probe=7d67`). Audited Codex's uncommitted changes over htop `c3a0d73c`: `IntelGPU.c`, `tools/intel-gpu-sample.c`, `tools/test-intel-gpu.py` and the docs.

The fix for 25 is correct. On xe only, with an unchanged device that was active on the previous refresh, the sampler still checks `runtime_status` on every refresh. It repeats the previous sample until `power/autosuspend_delay_ms` + 50 ms has passed since the last read finished. The delay falls back to 1000 ms when the file is missing or malformed, and a delay of 0 or less permits every read. Rates stay correct across skipped refreshes because xe measures against GPU timestamps. i915 is unchanged. The fake-clock scenario covers held refreshes, the due refresh, sleep and wake, a device change, and disabled, zero, short, malformed and missing delays. The fix for 26 drops only the exact Mesa "experimental with Xe KMD" line, only for the graphics workload; real errors and other Mesa warnings still fail.

- Build: no warnings. STYLE OK. `git diff --check` is clean in both repos.
- `test-intel-gpu.py --mutations` with the live part on xe: 268 ok, ALL PASSED. "Intel graphics workload succeeds" now passes. Live peaks: encode 32.3%, decode 17.8%, graphics 100%. `test-sampler.py`: 198 ok, ALL PASSED.
- My own runtime PM measurement (30 s windows, standalone sampler, `power/runtime_active_time`):

| Sampler | Refresh | iGPU awake |
|---|---|---|
| none | — | 23.1% / 23.5% (before and after) |
| committed `c3a0d73c` | 0.5 s | 96.1% |
| working tree (fix) | 0.5 s | 24.5% |
| working tree (fix) | 1.5 s | 26.4% |
| working tree (fix) | 0.25 s | 26.7% |

Findings 25 and 26 are confirmed resolved.

### 27 (P3) — a `resuming` runtime status shows every Intel meter as N/A for one refresh

`IntelGPU_refresh()` treats only `suspended` and `suspending` as sleep. `resuming` falls through to `INTELGPU_UNAVAILABLE`, so the heading reads `Intel iGPU: N/A` and every Intel meter reads N/A for that refresh instead of `sleep`. Polling `runtime_status` every 2 ms for 20 s on xe gave active 1942, suspending 24, suspended 7447, resuming 31. The sampler runs above reported `unavailable` on 1 of about 60 and 1 of about 120 ticks. This behavior predates the fix and is shared with i915, but xe's 1000 ms autosuspend (i915 here: 10000 ms) makes it much more frequent. The AMD sampler already treats `resuming` as sleep (finding 17). Suggested fix: add `resuming` to the sleep states, and add a fixture step that sets `runtime_status` to `resuming` and expects `suspended`.

Notes: the fix is not packaged yet. `c3a0d73c` is already pushed, so it needs a new htop commit, a re-export (new patch 0017) and pkgrel 18 rather than a squash. A cosmetic nit: README's new xe paragraph uses a curly apostrophe (`driver’s`), while the rest of the file uses straight ones.

Limits: one machine, one xe boot. i915 runtime PM was not re-measured.

## 2026-11-19, Codex — verified fixes for Xe findings 25 and 26

For finding 25, the sampler uses the Xe device's autosuspend delay and gives the driver another 50 ms to suspend after the last clock and fdinfo scan. Short refreshes reuse the previous readings while checking device identity and runtime status every time. A visible sleep clears the cache and client baseline. The next active sample starts immediately. A missing or malformed delay uses 1000 ms. A valid nonpositive delay allows every refresh. The Xe limiter uses Linux CLOCK_MONOTONIC for both the elapsed-time check and the scan completion timestamp.

Measured runtime_active_time on the 270K Plus with Xe bound, a 1000 ms autosuspend delay, and the desktop running. Each 14-second window started with one open/close of the render node. The standalone samplers polled every 0.5 s.

| Reader | Time awake |
|---|---|
| No sampler, two windows | 24.8%, 25.2% |
| 3.5.3-17 sampler | 100.0% |
| Fixed sampler, two windows | 39.3%, 26.1% |

For finding 26, the test ignores the exact Mesa Xe KMD experimental warning during the graphics workload. It still checks the FFmpeg exit status, other stderr output, and GPU execution on the selected PCI device. The original test failed only on this Mesa warning even though graphics reached 100%.

The Intel suite passed 268 assertions on Xe, including all three mutation checks. Live peaks were 32.2% encode, 32.2% decode and 100% graphics. The AMD suite passed 198 checks. The build and style checks passed. At a 0.5 s refresh, the sanitized htop displayed 32% video, 2000 MHz and 85.6 MiB during encoding, with no sanitizer reports. The released patch series reproduced the baseline and accepted the working-tree source diff cleanly. The installed package is 3.5.3-17. The fixes are uncommitted. Only the 270K Plus was used for this Xe hardware verification.

## 2026-11-19, Claude Code (Claude Opus 5.5) — first live run on xe

The user booted 7.3.4 once with `i915.force_probe=!7d67 xe.force_probe=7d67`. The iGPU (`8086:7d67`) bound to `xe` (the kernel log says "Found meteorlake (device ID 7d67)"). GuC 70.53.0, HuC 8.5.4 and GSC 102.1.15.1926 loaded on GT0 (render) and GT1 (media). The log shows no xe warnings or errors; the only error lines are the known amdgpu RA24 noise. The `/dev/dri` nodes swapped for that boot: the iGPU was `card0`/`renderD129` and the 9070 XT `card1`/`renderD128`. Everything that uses `by-path` (the tests, mpv) was unaffected. Layout: `tile0/gt0/engines` = bcs ccs rcs, `tile0/gt1/engines` = vcs vecs, `freq0` max 2000 MHz on gt0, autosuspend delay 1000 ms. Tested: htop `c3a0d73c` source and the installed htop-gpu 3.5.3-17.

Results:

- `test-intel-gpu.py --mutations` on xe: 249 of 250 ok. The live peaks match i915: encode 32.7%, decode 18.2%, graphics 100%. Memory and the requested clock were valid in every workload, and the run exited cleanly under ASan/UBSan. The one failure is finding 26 below.
- Installed htop-gpu 3.5.3-17, run with a copy of the user's htop-gpurc during an `h264_vaapi` encode: heading `Intel iGPU`, usage 0%, clock 2000MHz, mem 85.6M, Vid 32% E/D. These match the i915 capture. The user's config hash was unchanged.
- So the xe paths (cycle ratios, system + GTT memory, `freq0` clock on the render GT, separate media GT) work on real hardware.

### 25 (P3) — refreshes faster than xe's autosuspend delay keep an idle iGPU awake

On xe, reading a client's fdinfo cycle counters or `tile0/gtN/freq0/{cur,max}_freq` while the GPU is active resets its 1000 ms autosuspend timer. The sampler never wakes a suspended GPU, since it checks `runtime_status` first. But once the GPU is awake, sampling faster than about once per second keeps it awake. Measured with `power/runtime_active_time` over 30 s windows, with the user's desktop running:

| Reader (only while active) | iGPU awake |
|---|---|
| none (baseline, measured twice) | 17–23% |
| standalone sampler, every 1.5 s (htop's default delay) | 27% |
| standalone sampler, every 0.5 s | 80% |
| fdinfo reads alone, every 0.5 s | 78% |
| `cur_freq` + `max_freq` reads alone, every 0.5 s | 100% |

At htop's default delay the effect is small. With `-d 5` or a 0.5 s delay set in htop's settings, an idle xe iGPU stays awake most of the time. i915 was not measured in this boot; its autosuspend delay here is 10000 ms. A possible fix: on xe, read the clock and client counters no more often than `power/autosuspend_delay_ms` (keep the previous values in between), or document the trade-off. Both reads count, so throttling only one is not enough.

### 26 (P3) — the live graphics check fails on Mesa's xe warning

`live_tests()` requires an empty stderr from every workload. On xe, Mesa's Intel Vulkan driver prints "Support for this platform is experimental with Xe KMD, bug reports may be ignored.". So "Intel graphics workload succeeds" fails even though FFmpeg exits 0 (confirmed by running the same command alone) and the sampler measured 100%. Suggested fix: drop known Mesa warning lines (`MESA: warning: ...` about Xe KMD support) before the empty-stderr check, and keep the exit-code check.

Limits: one boot, one machine, i915 runtime PM not measured. The device was force-probed, which Intel and Mesa both call experimental for this platform.

## 2026-11-19, Claude Code (Claude Opus 5.5) — independent verification of the finding 24 fix

Audited the uncommitted 3.5.3-17 tree after Codex's fix. The only source change since my previous audit is in `IntelGPU_parse()`. Non-`drm-` lines are skipped except `flags`, which is parsed as octal and checked for `O_PATH` (with `<fcntl.h>` added). A record with `O_PATH` set and no `drm-` key returns 0, meaning not a client. All other generic-only or partial records still return -1, so finding 23 stays fixed.

Findings: none. Finding 24 is confirmed resolved.

- Live re-run of my finding 24 probe on the 270K Plus (i915, light `h264_vaapi` encode, ASan/UBSan standalone samplers, 5 ticks each). The pre-fix sampler showed N/A / N/A / incomplete with an `O_PATH` holder, with and without `O_CLOEXEC`. The fixed sampler showed 0 / 2.1–2.2% / complete in both cases, the same as with no holder. A real idle `O_RDWR` handle gave valid zeros on both.
- Tests: the new stateful scenario captures real kernel fdinfo from an `O_PATH` handle. It covers a path handle beside a real client, the path handle alone (idle zeros), malformed octal flags and partial DRM metadata, the last two staying unknown.
- Build: no warnings. STYLE OK (IWYU accepts `<fcntl.h>`). `git diff --check` is clean in both repos.
- `test-intel-gpu.py --mutations`: 250 ok, ALL PASSED, all three negative controls caught. Live peaks: encode 33.3%, decode 18.5%, graphics 100%. `test-sampler.py`: 198 ok, ALL PASSED.
- Packaging: applying the PKGBUILD's 16 patches in order to a fresh `git archive 3.5.3` produced no rejects, the result is byte-identical to the working `IntelGPU.c`, and all 16 checksums match.

Limits: only i915 on the 270K Plus was tested live. xe uses the same parser path but was not run against a real `O_PATH` holder. No package was built or installed (installed: 3.5.3-16).

## 2026-11-19, Codex — verified fix for finding 24

The sampler ignores a matched descriptor when its Linux fdinfo contains valid octal flags with O_PATH set and has no DRM fields. An ordinary descriptor with missing client statistics still makes utilization unavailable, as required by finding 23.

The new regression reads flags from a real path-only descriptor. Three assertions failed on the previous sampler. With the fix, an idle device reports zero, a separate busy client reports 20% render and 10% video, and malformed flags or partial DRM data still report unavailable. On the Core Ultra 7 270K Plus, the original sampler reported video unavailable while the fixed sampler measured encoding activity in seven of eight paired samples with the same path-only handle open.

All 250 Intel and 198 AMD checks passed, along with build, style and sanitized display checks. The 16 package patches applied cleanly with matching checksums and reproduced the tested IntelGPU.c byte for byte. Tiger Lake and Rocket Lake coverage used fixtures.

## 2026-11-19, Claude Code (Claude Opus 5.5) — audit of the finding 23 fix

Audited the uncommitted 3.5.3-17 tree after Codex's finding 23 fix. The only source change since my previous audit is in `IntelGPU_parse()`. My previous re-audit missed finding 23, which was pre-existing parser behavior, and Codex's catch is valid.

The fix is correct for the case it targets. `driver` and `pci` now point into the `strsep`-split buffer, which stays valid for the whole call. An explicit foreign driver or a valid foreign PCI address is still ignored. A missing driver, a missing or malformed PCI address, or a missing client ID now returns -1, so the scan is marked incomplete instead of reading as a false zero.

### 24 (P3) — an O_PATH handle on the iGPU node makes usage and video N/A

`IntelGPU_drmFile()` matches descriptors by `stat()` on `/proc/<pid>/fd/<n>`, which follows the link to the device node. An `O_PATH` descriptor on `/dev/dri/renderD128` therefore matches: it is `S_ISCHR` with rdev 226:128. Its fdinfo has only `pos`, `flags` (`012000000`, i.e. `O_PATH|O_CLOEXEC`), `mnt_id` and `ino`, because it never went through `drm_open()` and is not a DRM client. After the finding 23 fix, `IntelGPU_parse()` returns -1 for it, and the whole device's usage and video stay N/A with `incomplete=true` for as long as the handle is open.

Reproduced live on the 270K Plus (i915), with a light `h264_vaapi` encode keeping the iGPU active and the standalone ASan/UBSan sampler built from both sources:

| Sampler | O_PATH holder | usage / video / incomplete (5 ticks) |
|---|---|---|
| pre-fix (previous audit's `IntelGPU.c`) | no | 0 / 2.0–2.8% / false |
| pre-fix | yes | 0 / 2.0–2.6% / false |
| fixed | no | 0 / 2.0–2.7% / false |
| fixed | yes | **N/A / N/A / true** on every tick |

Any unprivileged process can trigger this for everyone viewing the meters, but no such handle exists on this machine today: a scan of the 9 readable Intel DRM descriptors found none with generic-only fdinfo. Suggested fix: when the fdinfo has no `drm-` keys and its `flags` field has `O_PATH` (`010000000`) set, return 0 (not a client), and keep -1 for other generic-only records. Add a fixture with `flags: 012000000` next to the existing generic-only cases, and assert valid zeros under one running sampler.

### Other checks

- Build: no warnings. STYLE OK. `git diff --check` is clean in both repos.
- `test-intel-gpu.py --mutations`: 244 ok, ALL PASSED, all three negative controls caught. Live peaks: encode 33.0%, decode 18.5%, graphics 100%. `test-sampler.py`: 198 ok, ALL PASSED.
- Packaging: applying the PKGBUILD's 16 patches in order to a fresh `git archive 3.5.3` produced no rejects, the result is byte-identical to the working `IntelGPU.c`, and all 16 checksums match.
- Side observation: an idle probe without a workload showed N/A with zero clients and nothing denied. That is the iGPU runtime-suspending between samples, which is expected and not a defect.

Limits: only i915 on the 270K Plus was tested live. The O_PATH case was not tried on xe, where the parser path is the same. No package was built or installed (installed: 3.5.3-16).

## 2026-11-19, Codex — finding 23 resolved

Fixed the 3.5.3-17 working-tree sampler's handling of an open descriptor matched to the selected GPU. Missing identity fields or a malformed PCI address now mark the scan incomplete. A positively identified foreign device is still ignored. When the descriptor is the only potential client, usage, video and allocated memory remain unavailable until identity returns or the descriptor closes. The independent GPU clock keeps updating.

Six new assertions failed on the pre-fix sampler. After the fix, both original Tiger Lake and Rocket Lake probes showed N/A on initial and repeated generic-only samples, 550 MHz throughout, 30% usage and 1 MiB after identity returned, N/A after identity was lost again, and valid zeros after closure. All 34 simulated family/driver sequences and 40 exclusion checks passed against the patch-reproduced source.

The normal build, style check, 244 Intel assertions, 198 AMD assertions and a whole-program sanitized display passed. Live i915 testing on the 270K Plus confirmed FFmpeg work on the selected device. The new families and xe were exercised with fixtures. All 16 ordered package checksums matched and the patches reproduced the tested sampler without offsets or fuzz. Source, tests, packaging and records remain uncommitted. Installed version is 3.5.3-16.

## 2026-11-19, Codex — audit of the Tiger Lake and Rocket Lake extension

Reviewed the uncommitted 3.5.3-17 working tree over outer `e593453` and htop `943464c0`. Tested IntelGPU.c as reproduced by the package series (SHA-256 `05037101398e88318cb926879d55be29e6366795452e2d85090fec83160d8024`).

### 23 (P2, subsequently resolved) — an open Intel GPU descriptor with only generic fdinfo yields false zero readings

At `src/htop/linux/IntelGPU.c:493`, a missing driver or PCI field returns the same result as an explicitly foreign client. The scanner has already matched the descriptor's character-device number to the selected GPU. It silently skips the record and can finish the scan with zero clients and complete coverage. Memory then displays zero bytes, and after the first scan usage and video both display 0%. This is a pre-existing parser behavior affecting the newly recognized devices. Older i915 implementations predate the DRM-specific client fields. [Kernel commit introducing i915 fdinfo client statistics](https://git.zx2c4.com/wireguard-linux/commit/Documentation?id=055634e4b62f109a47727c2c50586e2e318595a9)

Reproduced with Tiger Lake 8086:9a49 and Rocket Lake 8086:4c8a in separate stateful sanitized runs. With a matching render descriptor open, give its readable fdinfo only pos, flags, mnt_id and ino. After two ticks both families reported zero usage, video and memory, a valid 550 MHz clock and incomplete=false. Restoring complete DRM fields gave 30% usage and 1 MiB on the next usable interval. Removing the DRM fields again while keeping the descriptor open immediately returned all three client meters to zero. Closing the descriptor was the control in which zero was appropriate.

A fix should mark a matched descriptor lacking a usable identity as incomplete, retain valid independent clock data, and continue ignoring explicitly foreign identities. Cover the generic-only, restored, and genuinely closed states in one running sampler.

### Other checks

- Expanded the kernel header macros and checked the installed 7.3.4 i915 and xe module aliases. All 17 new IDs are present on both driver lists. All 109 IDs in the sampler match the intended kernel family lists exactly.
- Built the standalone sampler from patch-reproduced source with ASan/UBSan. Across all 34 new device/driver pairings, independently verified graphics, video, clock, allocated memory, loss of the memory field with client identity intact, and suspend/wake rebaselining. All 40 DG1 and Ice Lake device/driver exclusion checks passed.
- Development build and style checks passed. All 232 existing Intel and 198 AMD assertions passed. Live i915 peaks on the 270K Plus were 100% graphics, 32.9% encode and 18.5% decode. All 16 ordered package patch hashes matched and patches applied to upstream 3.5.3 without offsets or fuzz.
- The two new families and xe were tested with synthetic sysfs and proc data. No physical Tiger Lake or Rocket Lake GPU was available, and no binary package was installed.

## 2026-11-19, Claude Code (Claude Opus 5.5) — re-audit after the Tiger Lake and Rocket Lake extension

Audited Codex's follow-up on the same uncommitted 3.5.3-17 tree. The only source change since my previous audit is 17 added IDs in `IntelGPU_supported()`; no logic changed.

Findings: none.

- IDs: expanding the 7.3.4 kernel's TGL, RKL and ADL through NVL-P macros with `cpp` gives 109 distinct IDs, exactly the sampler's table. None of the DG1 IDs are in it, and Ice Lake (`0x8a52`) is excluded as the tests expect.
- Tests: the new family loops call each lambda immediately inside `scenario()`, so late binding is not an issue. Tiger Lake covers the legacy card-level clock, Rocket Lake covers the per-GT layout, and both cover render-only usage, video and memory.
- Build: no warnings. STYLE OK. `git diff --check` is clean in both repos.
- `test-intel-gpu.py --mutations`: 232 ok, ALL PASSED, all three negative controls caught. Live peaks: encode 33.0%, decode 18.5%, graphics 100%. `test-sampler.py`: 198 ok, ALL PASSED.
- Packaging: applying the PKGBUILD's 16 patches in order (with the renamed `0016-linux-extend-Intel-integrated-graphics-support.patch`) to a fresh `git archive 3.5.3` produced no rejects. The result is byte-identical to the working `IntelGPU.c`. All 16 checksums match.

My previous note that Tiger Lake and Rocket Lake were excluded by design no longer applies. The other notes still stand: commit the source and re-export 0016, and check Xe runtime PM on real hardware.

Limits: Tiger Lake, Rocket Lake and Xe are covered by fixtures only. No binary package was built and nothing was installed (installed: 3.5.3-16).

## 2026-11-19, Codex — Tiger Lake and Rocket Lake compatibility verification

Tested the uncommitted 3.5.3-17 sampler and package recipe. The sampler table exactly matches all 109 distinct IDs produced by expanding the supported family macros in this host's Linux 7.3.4 headers, including 11 Tiger Lake GT1/GT2 IDs and six Rocket Lake IDs.

Seven assertions in the extended tests failed against the preceding sampler. On the revised source, the stateful i915 fixtures for both families showed 35% render activity, 15% video and 2 MiB allocated. Tiger Lake exercised the legacy requested clock; Rocket Lake exercised the per-GT layout. Discovery checks also covered binding each family to xe and excluding DG1 and Ice Lake.

The normal build, style check, 232 Intel assertions (including three negative controls), 198 AMD assertions and a whole-program sanitized terminal capture passed. On the Core Ultra 7 270K Plus with i915, live graphics peaked at 100%, encode at 32.6% and decode at 18.6%. All 16 ordered patch checksums matched. Applying the package series to upstream 3.5.3 with zero fuzz reproduced the tested IntelGPU.c byte for byte. No new findings in these checks. Both newly added families and xe have fixture coverage only. Installed version is 3.5.3-16.

## 2026-11-19, Claude Code (Claude Opus 5.5) — independent audit of Codex's Intel iGPU compatibility work

Audited the uncommitted 3.5.3-17 working tree: outer `e593453` + local changes, htop `943464c0` + uncommitted `linux/IntelGPU.c` (the same file patch 0016 produces).

Findings: none in the sampler, tests or packaging.

Verified independently:

- PCI IDs: expanded the 7.3.4 kernel's `INTEL_{ADLS,ADLP,ADLN,RPLS,RPLU,RPLP,MTL,ARL,LNL,PTL,WCL,NVLS,NVLP}_IDS` with `cpp`. The 92 IDs match the sampler's table exactly (the header writes four NVL-P IDs as uppercase `0X`).
- Code review of the diff: the i915 path is unchanged except the render-only inventory and the legacy `gt_cur_freq_mhz` fallback. The Xe busy/total pairing, stall retention (finding 20), timer-reset rebaseline, compute-only GT selection (finding 21), system + GTT memory sum and driver/PCI filtering look correct.
- Build: no warnings. `tools/check-style.sh`: STYLE OK. `git diff --check`: clean in both repos.
- `test-intel-gpu.py --mutations`: 216 ok, ALL PASSED, all three negative controls caught, FFmpeg's Vulkan work was confirmed on the selected PCI device (finding 22). Live peaks: encode 32.9%, decode 18.0%, graphics 100%. `test-sampler.py`: 198 ok, ALL PASSED.
- Packaging: reapplied all 16 patches to a fresh `git archive 3.5.3` with `patch -Np1`, no fuzz and no rejects. The resulting `IntelGPU.c` is byte-identical to the working tree. All 16 PKGBUILD checksums match.

Notes, not defects:

- The htop change is not committed yet, and patch 0016 is a plain `git diff` with no commit header. Once it is committed, `tools/export-patches.sh` will regenerate 0016 and its checksum. Re-run the patch check afterwards.
- AGENTS.md "What this is" still described i915-only meters for this machine's iGPU, and this file's status header stopped at finding 14. Both were corrected later the same day.
- The live test now accepts any supported Intel PCI address instead of requiring `0000:00:02.0`. That is fine for portability.
- Untested on real Xe hardware: as far as I remember the kernel source (not checked here, since only headers are installed), Xe takes a runtime-PM reference when it reads fdinfo cycles and `freq0/cur_freq`. If so, refresh intervals shorter than Xe's autosuspend delay could keep an otherwise idle Xe iGPU awake. htop never wakes a suspended GPU, because it checks `runtime_status` first. This does not affect this machine, which uses i915.
- Tiger Lake and Rocket Lake are excluded by design even though their i915 fdinfo format is the same. That is a scope choice.

Limits: only the 270K Plus on i915 was tested on hardware. Xe was covered by fixtures only. No binary package was built and nothing was installed (installed: 3.5.3-16).

## 2026-11-19, Codex — findings 20–22 resolved in the 3.5.3-17 working tree

- **20.** Xe now retains the last usable busy/total pair while the GPU timestamp is stalled. The original four-sample probe gives N/A, N/A, 50%, 20%. Timer reset and missing-denominator cases also pass.
- **21.** The sampler inventories render and compute engines and locates the graphics GT using either class. The original compute-only fixture now shows 50% usage and 750 MHz with a 2000 MHz limit. The separate media GT and missing-counter cases are covered by permanent tests.
- **22.** The Vulkan test limits Mesa to the discovered PCI address and derives the Vulkan context from the corresponding VA-API render node. It checks FFmpeg’s own fdinfo for positive graphics work on that PCI device. That check passed live on the 270K Plus.

Verification: 216 Intel and 198 AMD assertions passed, including the Intel mutation controls. The normal build, style checks, original sanitized probes and whole-program sanitized terminal capture passed. All 16 ordered package checksums matched and the patch series applied to upstream 3.5.3 with zero fuzz, yielding the exact tested sampler. Live peaks on i915 were 100% graphics, 32.9% encode and 18.5% decode. Xe was exercised with fixtures. No dual-Intel system was available. The working tree and packaging patch are uncommitted. The installed package is 3.5.3-16.

## 2026-11-19, Codex — independent audit of Intel compatibility changes

Reviewed the uncommitted 3.5.3-17 recipe and sampler on outer `e593453` and htop `943464c0`. The reviewed IntelGPU.c SHA-256 is `130c418d52343dad9e88f1450374e72c303b63d05bd7338801285af859886b1f`. Findings 20–22 were open at this audit and resolved in the subsequent validation above.

### 20 (P2) — a stalled Xe timestamp can lose measured work

In `src/htop/linux/IntelGPU.c:638–656`, an unchanged total-cycle counter makes the current rate unavailable, but the code still saves the newer busy counter as the next baseline. In one running sanitized sampler, the (total, busy) pairs were (1000, 100), (1000, 150), (1100, 150), (1200, 170). The sampler returned N/A, N/A, **0%**, 20%. The two endpoints around the stall show 50 busy cycles over 100 total cycles, or **50%**. The shipped stalled-timestamp test keeps render busy unchanged at the stall and subsequently resets the timer, so it does not exercise this loss. Preserve the last usable pair during a stall and compute the next positive interval from that pair. Keep the existing separate behavior for timer resets.

### 21 (P3) — compute-only Xe configurations lose usage and clock

In `src/htop/linux/IntelGPU.c:675–678,811–815`, utilization and requested-clock discovery both require a render engine. The kernel documents a compute-and-copy-only engine configuration. A fake integrated Lunar Lake card with compute and copy classes exposed a 750 MHz requested clock, a 2000 MHz limit and compute counters increasing by 500 of 1000 cycles. The sampler calculated 50% compute internally but returned N/A for both user-visible meters. The render-only control returned 50% and 750 MHz. Consider a graphics GT with compute engines when locating the clock and sum the engine classes verified to exist. Preserve N/A for a missing reading from a class that does exist. This was reproduced with fixtures only. [Kernel Xe engine configuration](https://docs.kernel.org/gpu/xe/xe_configfs.html)

### 22 (P3) — the live Vulkan test can exercise a different Intel GPU

In `tools/test-intel-gpu.py:551–560,583`, the encode/decode commands use the discovered PCI render node. The Vulkan command instead selects the first device whose name contains “Intel”. The selected Mesa ICD can expose both integrated and discrete Intel GPUs. This can fail an idle iGPU test or pass on unrelated iGPU activity, because any positive sample satisfies the workload assertion. Confirmed by command inspection and FFmpeg's documented selection rule. This host has one Intel GPU, so the dual-Intel failure was not reproduced physically. A one-frame control using a VA-API context opened on the selected render node and a derived Vulkan context (`vulkan=gpu@bound`) succeeded here and FFmpeg reported Intel Graphics (ARL). [FFmpeg hardware device selection](https://ffmpeg.org/ffmpeg.html)

### Verification

- Development build and style check passed. The existing Intel suite passed 206 assertions including all three mutation controls. Live peaks on the 270K Plus were 100% graphics, 33.0% encode and 18.4% decode. The AMD suite passed 198 assertions.
- The independent Xe probes for 20 and 21 ran under ASan/UBSan and exited cleanly. Only the i915 hardware path received live validation.
- Independently expanded the integrated-family macros with the C preprocessor. The sampler matches all 92 distinct IDs in this machine's Linux 7.3.4 headers and covers all 76 listed for those families in its 6.18.60 headers.
- Checked all 16 ordered patch checksums and reapplied the recipe's patches with zero fuzz to a fresh archive of upstream htop 3.5.3. The resulting IntelGPU.c matched the audited file byte for byte. This verifies the patch series. The binary package was not rebuilt or installed.

## 2026-11-19, Codex — Intel integrated graphics compatibility

Reviewed the local changes over htop `943464c0` and outer `e593453`. The baseline accepted only i915 device 8086:7d67 and required both render and compute counters for graphics usage. The revised sampler recognizes 92 integrated graphics PCI IDs from the Linux 7.3 family lists. It discovers the bound driver, keeps clients scoped to the selected device, and uses an engine inventory to identify render-only graphics. Xe utilization uses busy and total GPU cycle deltas, and its memory readout combines the system and GTT allocation categories.

- The development build completed without warnings. Style checks passed. The final Intel suite passed 206 assertions, including three mutation controls, and the AMD sampler passed 198. No outstanding finding from these checks.
- Tests cover representative family IDs, discrete and pre-Alder Lake exclusions, deterministic mixed-driver selection, a render-only Alder Lake layout, Xe descriptor sharing, missing and stalled cycle denominators, timer reset, two video engines, sleep/wake, memory accounting and render/media GT selection. During development four fixture assertions caught a missing topology call in an intermediate build. All four pass in the tested source.
- On the 270K Plus with i915, graphics utilization peaked at 100%, encode at 32.5% and decode at 18.4%. A whole-program ASan/UBSan terminal capture using a disposable layout showed the sleeping state and, in a separate live run, 2000 MHz, 93.7M allocated and 16% video activity. No sanitizer diagnostic was logged.
- All 16 package patches matched their ordered checksums and applied to pristine htop 3.5.3 with zero fuzz. The resulting Intel sampler matched the tested development source byte for byte. The package recipe is 3.5.3-17. The system still runs 3.5.3-16.
- Other Intel hardware and the xe driver were exercised with synthetic sysfs and fdinfo only. Real Xe power behavior, cross-generation performance and a binary package build were outside this validation.

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


## Self-audit of the heading meters by Claude Code

Date: 2026-10-29, at the user's request ("perform an audit of the work you did").
Audited: the uncommitted `AMDGPUInfo` and `IntelCPUInfo` heading meters on htop
`bb4f7331` (`linux/AMDGPU.c/.h`, `linux/AMDGPUMeter.c/.h`, `linux/IntelRAPLMeter.c/.h`,
two registration lines in `linux/Platform.c`) and the outer changes (`tools/test-sampler.py`,
`PLAN.md`, `PLAN-AMD-DGPU.md`, `README.md`, `CHANGELOG.md`) on outer `fd4cd58`.
Installed `htop-gpu 3.5.3-12` does not contain them.

### 9. [P3] Docs say every meter has bar, text, graph and LED modes

`README.md` ("can show each one as a bar, text, graph or LED") and the `PLAN.md` Meters
paragraph ("switched between bar / text / graph / LED") now sit next to two text-only
headings. The `IntelGPUInfo` heading already made this untrue. Fix: say the headings are
text only. Also cosmetic: one overlong line in `PLAN-AMD-DGPU.md` item 1.

### 10. [P3] The CHANGELOG entry overstated the checks

It said "all five suites `ALL PASSED`", but `tools/test-check-style.sh` had not been run
(the rules only require it after touching `check-style.sh`, which this work didn't do),
and it counted 9 model-name cases where 10 were run. The same "all five" claim was made
to the user. `test-check-style.sh` has now been run: `ALL PASSED`. The entry is corrected.

### 11. [P3] Lowercase `(tm)` / `(r)` are not stripped from the CPU name

`IntelCPUInfoMeter_cleanName()` only matches `(R)` and `(TM)`, so older names keep them:
`AMD Athlon(tm) II X4 640 Processor`, `Intel(r) Pentium(r) 4 CPU 3.00GHz`. Not this
machine. Fix: compare with `strncasecmp()`.

### 12. [P3] Truncation can split a multi-byte character

The name is cut at 63 bytes, which can leave half a UTF-8 sequence (shown as `�`).
x86 `model name` strings are ASCII, so this is theoretical; noted, no fix proposed.

### 13. [P3] No committed regression tests for the headings

The heading states and the name cleanup were checked with captures, a one-off build that
reads a fake cpuinfo, and a scratch harness, none of which are in `tools/`. Only the card
name is covered by `test-sampler.py`. Fix: add the cleanup cases and the heading states
to the suites.

### Checked and found correct

- `getCaption` is called only by the meter draw modes in `Meter.c`, the same way upstream's
  `DynamicMeter_getCaption()` uses it, so `this->host` is valid. The AMD heading's sample
  read in it hits the per-tick cache. The returned pointers are the static card table,
  the static name buffer or the meter's own caption, never NULL.
- `maxItems = 0`, text-only meters with an empty `txtBuffer` are the same pattern as the
  audited `IntelGPUInfo`.
- Under one running ASan/UBSan htop on a fake tree, active → suspended (`Radeon RX 9070 XT:
  sleep`), active → unbound (`AMD GPU: N/A`), unbound → active and suspended → active (name
  back) were all right, with no sanitizer reports.
- The real `IntelCPUInfoMeter_cleanName()` was run under ASan/UBSan on 17 inputs: `(R)`/`(TM)`,
  ` @ GHz`, `12th Gen ...`, tabs and repeated spaces, `Intel(R` (malformed), `(R)(TM)` alone
  (empty, so the caption falls back to `CPU`), ARM, empty, buffer sizes 1-4. No overflow,
  and the space is dropped rather than written without room.
- Build without warnings, `STYLE OK`, and `ALL PASSED` from `test-sampler.py`, `test-rapl.py`,
  `test-intel-gpu.py --mutations`, `test-config-path.sh` and `test-check-style.sh`. The dev
  binary has no ASan or fake paths. `make -q` reports it stale, but a real `make` compiles
  nothing and the binary's checksum doesn't change; `config.h` and `stamp-h1` share a
  timestamp second.
- Upstream files: only the two `Platform.c` registration lines.

Notes, not findings: `IntelCPUInfo` shows any vendor's name while its UI name says Intel,
which matches the Intel-only CPU scope. The AMD heading used alone does a full AMD sample
per tick; next to the other AMD meters that sample is shared and costs nothing extra.

Not tested: interactive F2 Setup with the new meters, the installed package, the user's
real config. Nothing was committed, installed, or written to the user's configs.


## Resolution of findings 9, 11 and 13

Date: 2026-10-29, at the user's request ("Fix them"). By Claude Code. Uncommitted, on the
same baseline as the self-audit.

- 9: `README.md` and the `PLAN.md` Meters paragraph now say the headings (`AMDGPUInfo`,
  `IntelCPUInfo`, `IntelGPUInfo`) are text only. The overlong `PLAN-AMD-DGPU.md` line is
  reflowed.
- 11: `IntelCPUInfoMeter_cleanName()` matches `(R)` / `(TM)` with `strncasecmp()`
  (`<strings.h>`, as upstream's `Panel.c` does), so `AMD Athlon(tm) II X4 640 Processor`
  becomes `AMD Athlon II X4 640 Processor`.
- 13: new `tools/test-headings.py`. It rebuilds `linux/AMDGPU.c`, `linux/AMDGPUMeter.c` and
  `linux/IntelRAPLMeter.c` with a fake cpuinfo, a fake sysfs root and ASan/UBSan (then
  rebuilds them normally), and runs the real htop in a pty with only the two headings:
  14 cpuinfo cases (text and cyan color), six AMD card states including four changes under
  one running htop, a sanitizer report check, and a live check of the normal binary. Listed
  in `AGENTS.md` Checks.
- 12 stays as accepted: x86 model names are ASCII.

Validation:
- Before the fix, `test-headings.py` failed exactly the two lowercase cases
  (`AMD Athlon(tm) ...`, `Intel(r) Pentium(r) ...`) and passed the other 24 checks. After
  the fix: `ALL PASSED`.
- Negative control: with `AMDGPUInfo` mutated to always show its static caption and no
  status text, all 8 AMD checks failed. The source was restored byte for byte (`cmp`).
- Build without warnings, `STYLE OK`, and `ALL PASSED` from `test-sampler.py`,
  `test-rapl.py`, `test-intel-gpu.py --mutations`, `test-config-path.sh` and
  `test-check-style.sh`. The dev binary has no sanitizer or fake paths, and a real `make`
  compiles nothing.

Limits: the cpuinfo and card states are fakes (real card files copied by `fake-sysfs.py`);
interactive F2 Setup, the installed package and the user's config were not tested.
Nothing was committed, installed, or written to the user's configs.

Release (same day, at the user's request): committed as htop `44265679` (`linux: add AMD
GPU heading meter`) and `798d8cfa` (`linux: add CPU heading meter`); the first one was
built on its own before the second was committed. Patches re-exported (0011, 0012 new;
0001-0010 differ only in their `[PATCH n/12]` numbering), pkgrel 13. `makepkg -fC` built;
`namcap` reports the same three lines as 3.5.3-12. Installed `htop-gpu 3.5.3-13` with the
user's sudo: the installed binary matches the package, `pacman -Qkk` shows 0 altered files
for htop-gpu and htop. The user's `htop-gpurc` was backed up
(`htop-gpurc.bak-2026-10-29_21-59-40`) with no htop running, then got `IntelCPUInfo`
above `CPU(1)` and `AMDGPUInfo` above `AMDGPUUsage`, both in text mode. A capture of the
installed binary with a copy of it shows both headings, and the meter lines survived
htop's rewrite of the copy.


## Full patch audit: 2026-11-10

Auditor: Codex. Requested review of the project's patches; no fixes requested.
The plan listed `In progress: nobody` at entry. Both repositories were clean.

### Audited version and scope

- Outer repository: `fda534892c8ed76f09a2ca7c452b50489ec6d637`.
- htop source: `798d8cfacbc99077aad2147f5acdad1fd50d1fb6`, all 12 commits above tag `3.5.3`.
- Package definition and installed package: `htop-gpu 3.5.3-13`; stock package: `htop 3.5.3-1.1`.
- Reviewed AMD sampler/meters, Intel iGPU sampler/meters, Intel RAPL/CPU heading,
  configuration seeding, upstream registration/build integration, package patches,
  and validation tools. Reviewed the design and prior findings before classifying issues.
- All 12 patch SHA-256 values match `PKGBUILD`. Applied the full series to an isolated
  export of tag `3.5.3`, with fuzz disabled: no offsets or fuzz; all 16 changed source
  files match source HEAD byte for byte. `git diff --check 3.5.3..HEAD` is clean.

### 14. [P3] Heading color tests inherit an environment that disables colors

Location: `tools/test-headings.py:69-70`; assertions: lines 134 and 144.
Related behavior: `tools/htop-capture.py:15` preserves the environment;
upstream `src/htop/CommandLine.c:148-150` honors nonempty `NO_COLOR`.

The heading suite assumes cyan output but starts the capture subprocess without
controlling `NO_COLOR`. In this audit environment, `NO_COLOR=1` was already set.
The documented `python3 -I tools/test-headings.py` invocation therefore exited 1
with 20 false failures: all 14 CPU cases and all six AMD state cases printed the
correct text, but their captured color was `[default]` instead of `[cyan]`.
The other five assertions passed, including the sanitizer-report check.
This is a test-isolation defect, not incorrect heading rendering: htop is correctly
honoring its no-color setting. Python's isolated mode does not remove this variable.

Reproduction on the unmodified source:

- `python3 -I tools/test-headings.py` with inherited `NO_COLOR=1`: 20 failures.
- `env -u NO_COLOR python3 -I tools/test-headings.py`: exit 0, all 25 checks pass.

Suggested correction: pass a copy of the environment with `NO_COLOR` removed to
this color-specific suite's capture subprocess. Preserve the general capture
helper's environment handling so it can still inspect deliberate no-color output.
Validate the suite with the parent `NO_COLOR` both set and unset.
No correction was implemented during this audit.

### Validation results

Logs are retained locally under ignored `test/audit-2026-11-10/`.

| Check | Result |
| --- | --- |
| `make -C src/htop -j8` | Exit 0; no warnings emitted (initial build already current) |
| `tools/check-style.sh` | `STYLE OK` |
| `tools/test-check-style.sh` | `ALL PASSED`, 7 checks |
| `tools/test-config-path.sh` | `ALL PASSED`, 33 checks; disposable homes/configs |
| `python3 -I tools/test-sampler.py` | `ALL PASSED`, 106 checks, including fake-state recovery and live AMD encode |
| `python3 -I tools/test-rapl.py` | `ALL PASSED`, 49 checks, including live idle/busy power |
| `python3 -I tools/test-intel-gpu.py --mutations` | `ALL PASSED`, 158 checks, including three negative controls and live Intel encode/decode/graphics |
| `python3 -I tools/test-headings.py` | 20 false color failures with inherited `NO_COLOR=1`; see finding 14 |
| `env -u NO_COLOR python3 -I tools/test-headings.py` | `ALL PASSED`, 25 checks |

Live observations: AMD video activity reached 100%, with vclk/dclk reaching
2933/2200 MHz. Intel encode/decode peaks were 29.3%/35.1%, and the graphics workload
reached 100%. CPU package power increased from approximately 16.34 W idle to
125.80 W under the brief all-core workload. All sampler sanitizer checks passed.
The heading suite rebuilt the relevant sources with ASan/UBSan, checked real htop
output against fake cpuinfo and changing card state, and restored the normal binary.
No sanitizer reports occurred; the suite verified that the normal binary contained
neither its fake paths nor ASan instrumentation.

Additional independent isolated sampler checks passed under ASan/UBSan:

- AMD: active to suspended while a dynamic attribute was replaced with a blocking
  FIFO, then hwmon renumbering during suspension and recovery on wake. No blocked
  dynamic read; temperatures and clocks recovered; clean exit.
- RAPL: two packages, permission denial/recovery and malformed energy/recovery.
  Fresh baselines and combined 30 W / 375 W results were correct; clean exit.

An artificial individual-fdinfo denial despite a readable shared alias produced
conservative unavailable Intel rates. Ordinary procfs does not expose those
per-file chmod permissions; a real scan race was not reproduced. The design
allows unavailable samples after failed reads, so this was not classified as a
new defect.

### Conclusion, remaining limits, and preservation

One new low-priority test defect (14); no new actionable runtime defect confirmed.
Prior finding 7 (later CPU packages ignored after initial discovery) remains deferred
at the user's request. Finding 12 (possible UTF-8 truncation in the CPU heading)
remains accepted. This audit does not change either decision.

Real runtime suspend/resume, physical device hotplug, hardware outside the documented
RX 9070 XT / supported Intel iGPU scope, and an external Mission Center comparison
were not tested. No interactive F2 walkthrough or new whole-program sanitizer run
covering every meter mode was performed. Sanitizer coverage here comes from the
sampler suites, isolated probes, and the heading suite's instrumented sources.
The package was not rebuilt or installed, and the installed binary was not used
as the test target; package verification here covers patch integrity/application.

Only `AUDIT.md`, `CHANGELOG.md`, and `PLAN.md` were edited. Source code and exported
patches remain unchanged; the source working tree is clean. Test/build artifacts
are ignored. User configurations and system settings were not edited. No commit,
push, package installation, or dependency installation was performed.


## Resolution of finding 14 (2026-11-10)

At the user's request, Codex updated `tools/test-headings.py` to remove `NO_COLOR`
from a copy of the environment passed to its capture subprocess. This gives the
heading assertions the same color output regardless of the caller's preference.
The general capture helper continues to honor the caller's environment.

Both `NO_COLOR=1 python3 -I tools/test-headings.py` and
`env -u NO_COLOR python3 -I tools/test-headings.py` passed all 25 assertions,
including the ASan/UBSan report check and the live heading checks. The development
build, style check, and AMD sampler suite also passed. Logs are under ignored
`test/audit-2026-11-10/fix-14/`.

Validation used htop source `798d8cfa`. Only the heading test and project records
were edited. The checks covered the development binary and the heading suite's
fake states. No package rebuild or installation, real suspend, or hardware
hotplug was tested.


## Local package verification (2026-11-10)

Codex rebuilt `htop-gpu 3.5.3-13` for x86_64 at the user's request from outer
commit `cc2f286` and the existing PKGBUILD. makepkg verified the cached upstream
3.5.3 source and all 12 patch checksums. The output is
`packaging/builds/cc2f286/htop-gpu-3.5.3-13-x86_64.pkg.tar.zst`.
The archive SHA-256 is
`c63b0afc1d0eeee6a5fa18d7c0fe17da2a70b2e27480b9579ca90d4df0be4670`.

- Pacman read the archive and resolved it in print-only mode. Its five installed
  files do not collide with the stock htop package's files.
- The extracted executable reported `3.5.3-13-gpu`, matched the installed
  executable byte for byte, and displayed the CPU, AMD GPU, and Intel iGPU
  headings in a throwaway terminal config. All 33 configuration path checks passed.
- namcap diagnostics matched the previous 3.5.3-13 archive. The existing
  hicolor-icon-theme diagnostic refers to a dependency already installed here.
  The other diagnostics concern implicit glibc and possibly unnecessary libnl.

No new findings. Logs are under ignored `test/package-cc2f286/`. This check
used the extracted executable and a read-only pacman transaction. It did not
perform an installation, replace the earlier archive, or test another host.


## Package 3.5.3-14 check (2026-11-11)

Claude Code (Claude Fable 5.2) built `htop-gpu 3.5.3-14` with `makepkg -fC` from
htop `f842f486` (patch 0013, RDNA 2+ dedicated cards) after the source checks in
the CHANGELOG entry of the same date (build without warnings, `STYLE OK`,
`test-sampler.py` 161 checks and `test-headings.py` 25 checks, both ALL PASSED
on the development tree before the commit). Archive SHA-256:
`c41e0be5df7228ed733efab67d939159b29676fefbe1ced4ac7ffcd26f0e34fc`.

- Patches 0001-0012 differ from 3.5.3-13 only in their `[PATCH nn/13]` subject
  numbering.
- The extracted executable reports `3.5.3-14-gpu`, contains the `amdgpu.ids`
  path, and shows `Radeon RX 9070 XT` with all AMD meters live in a throwaway
  config. The archive holds the same five `htop-gpu` files as before.
- namcap reports the same three diagnostics as 3.5.3-13 (hicolor-icon-theme,
  implicit glibc, possibly unnecessary libnl).

No new findings. Limits: the test suites ran on the development tree, not on
the packaged executable; no installation; no real RDNA 2/3 or Navi 44 card (fake
trees only); the config path suite was not rerun (`Settings.c` untouched).

Installed 2026-11-11 at the user's request. `pacman -Q htop-gpu` reports
3.5.3-14, `/usr/bin/htop-gpu` matches the package executable byte for byte and
shows `Radeon RX 9070 XT` with all AMD meters live in a throwaway config. Stock
`htop` 3.5.3-1.1 is untouched.


## RDNA 2+ implementation audit (2026-11-11, Codex)

Reviewed htop `f842f4863fabb061e000ac12bb21a4fd870d33f7`, outer `58b8135`
(including `54c5ad6`), exported patches 0001–0013, and the installed 3.5.3-14
package. Scope: Claude's new card discovery, names, VCN fallback, static-value
retry policy, clock scaling, tests, and packaging. Two new findings remain open.
No runtime source or tests were changed by this audit.

### 15. [P2] Directory access errors become permanently missing sensors

Locations: `src/htop/linux/AMDGPU.c:132-144`, `:294-307`, `:477-480`.

`AMDGPU_exists()` treats every failed `access(F_OK)` as absence. A file can be
present while `access()` fails with EACCES because an ancestor directory is not
searchable. The new retry logic then counts this access error toward its five
absent refreshes instead of retrying it as a failed read.

Reproduction (one running ASan/UBSan sampler, copied sysfs only):

1. Make the copied `hwmonN` directory mode 0600 before the first sample. Its
   parent can still be enumerated and the directory itself exists, but reading
   or checking any child attribute returns EACCES.
2. Take six samples, then restore the directory to mode 0755.
3. Temperatures, sclk, mclk and fanMax remain unavailable on subsequent samples.
   Power resumes immediately (28 W in the probe), proving that the tree is
   readable again. The cached zero label indices and missing fan maximum are
   never refreshed: `access(hwmonDir, F_OK)` succeeds, so rediscovery does not run.
4. Restarting the sampler restores all these readings. Compiling the parent
   source (`f842f486^`) and applying the same permission sequence also restores
   them in the original process, confirming this is a regression. Denying only
   the fan1_max file's read permission is a passing control: that error recovers.

Impact: a temporary directory access failure can leave multiple meters at N/A
until restart or hwmon replacement, including on the RX 9070 XT. The existing
new tests use garbage contents to represent read failure, which does not
exercise a failed existence check.

Suggested correction: preserve error reasons and distinguish a confirmed
missing path (ENOENT) from EACCES and other failures; do not let an unconfirmed
absence exhaust the retry window. Add the directory-permission recovery case
under one process, alongside the existing absent/file-content cases.

### 16. [P3] First clock reading prevents recovery of a failed clock scale

Locations: `src/htop/linux/AMDGPU.c:429-433`, `:504-505`.

On cards without the Navi 48 seed, `pp_dpm_sclk` is retried only while
`sclkPeak` is NAN. If the first read fails but `freqN_input` is readable, the
same refresh sets `sclkPeak` to the current clock. The next refresh skips the
DPM read and can mark all static values complete, despite the earlier failure.

Reproduction (one ASan/UBSan sampler, synthetic GC 10.3.0): set current sclk to
600 MHz and pp_dpm_sclk's maximum to 2575 MHz, temporarily deny read permission
on pp_dpm_sclk, then restore it immediately after sample 1. Samples 2–9 keep a
600 MHz scale, rather than recovering to 2575 MHz. A new sampler reads 2575.
Thus the clock bar displays full at 600 MHz and subsequently scales to whatever
clock happens to have been observed, until restart. The MHz text stays correct.
The RX 9070 XT's explicit 3000 MHz seed avoids this path.

Suggested correction: track completion of the DPM seed read separately from
the highest observed clock. Retry a failed DPM read and combine a recovered
maximum with the existing peak without shrinking it. Test recovery with the
current-clock input already readable on the first sample.

### Validation and supporting evidence

- Build succeeded with no warning/error diagnostics; `tools/check-style.sh`
  reported STYLE OK. All 161 sampler and 25 heading assertions passed, including
  the live AMD VA-API workload and sanitizer checks. Both findings above are
  additional cases absent from those suites.
- Independent probes accepted all nine GC entries with the ids file missing,
  using their chip fallback names. File-level permission recovery passed;
  directory-level recovery failed as described. The parent sampler control
  recovered. Audit probes and parent control produced no sanitizer reports.
- Rechecked Linux v7.3's GC family/APU switches and decimal IP sysfs attributes
  in [amdgpu_discovery.c](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/amdgpu_discovery.c).
  The nine accepted GC versions are consistent with its dedicated-card/APU
  split. IP attributes expose cached discovery data.
- Rechecked VCN attribute visibility in
  [amdgpu_pm.c](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/pm/amdgpu_pm.c)
  and the RDNA 2 activity mapping in
  [sienna_cichlid_ppt.c](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/pm/swsmu/smu11/sienna_cichlid_ppt.c).
  RDNA 2 lacks vcn_busy_percent and maps its VCN activity into average_mm_activity.
  That driver plus smu_v13_0_0, smu_v13_0_7, and smu_v14_0_2 initialize metrics
  v1.3. Compiling the actual v1.3 and header struct declarations from
  [kgd_pp_interface.h](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/include/kgd_pp_interface.h)
  independently confirmed size 120 and offsets 20/60/62 on this x86_64 host.
- All 13 patch checksums match the PKGBUILD; applying the series to a fresh
  archive of tag 3.5.3 succeeds without fuzz/offsets and reproduces all 16 changed
  source files at HEAD byte for byte.
- Package SHA-256 remains
  `c41e0be5df7228ed733efab67d939159b29676fefbe1ced4ac7ffcd26f0e34fc`.
  All five installed payload files match the archive; pacman reports zero
  altered files. `/usr/bin/htop-gpu --version` reports `3.5.3-14-gpu`, and a live
  capture with a throwaway config shows the card name and AMD readings.

Logs, reproducible probes, cached kernel references and isolated builds are in
ignored `test/audit-rdna2-2026-11-11/`. Only AUDIT.md, CHANGELOG.md and PLAN.md are
changed in the tracked tree, left uncommitted. No package rebuild, installation,
commit or push; no user config or actual sysfs permissions changed. Only the
RX 9070 XT was checked on real hardware; other GPUs and access failures used
synthetic trees. Real suspend, firmware differences and hotplug remain untested.


## Resolution of findings 15 and 16 (2026-11-11, Claude Code)

Claude Code (Claude Fable 5.2) reproduced both findings first, as new cases in
`tools/test-sampler.py` run against htop `f842f486` (one running ASan/UBSan
sampler each, copied sysfs only): both failed as the audit describes (after the
hwmon directory became accessible again temps, sclk, mclk and fanMax stayed N/A;
the clock scale stayed at 600 MHz instead of 2575 MHz).

- **15, fixed.** `AMDGPU_exists()` became `AMDGPU_absent()`, true only when
  `access()` fails with ENOENT. Any other failed check (EACCES, ...) counts as a
  failed read, so it is retried on every refresh and never uses up the absent
  window. The same test decides the VCN fallback, so `gpu_metrics` stands in for
  `vcn_busy_percent` only when that file is confirmed missing.
- **16, fixed.** The top `pp_dpm_sclk` level is kept in `card.sclkSeed` (NAN
  until read) instead of being inferred from `sclkPeak`. It is read again while
  it is NAN and the read failed, and a late value raises `sclkPeak` but never
  lowers it. Completeness of the one-time values checks the seed, not the peak.

New tests (8 checks, suite now 169): hwmon directory mode 0600 for 6 refreshes,
then 0755, everything must be read; RDNA 2 tree with `pp_dpm_sclk` unreadable for
6 refreshes while the clock reads 600 MHz, then readable, peak must be 2575; a
2700 MHz clock seen before a late 2575 MHz level keeps the 2700 MHz peak.

Validation: build without warnings, `STYLE OK`, `test-sampler.py` ALL PASSED
(169, including live idle and VA-API encode), `test-headings.py` ALL PASSED (25).

Released the same day at the user's request: htop `7c2fe84b` (patch 0014),
package 3.5.3-15, SHA-256
`bcbd15105e4e55688079187203ac47b57d649f81cc008ae765cfba7470cea077`. Patches
0001-0013 only change their `[PATCH nn/14]` numbering; namcap gives the same
three diagnostics. Installed with `pacman -U`: `pacman -Q` reports 3.5.3-15,
`/usr/bin/htop-gpu` matches the package executable byte for byte and shows
`Radeon RX 9070 XT` with all AMD meters live in a throwaway config.

Limits: the suites ran on the development tree, not the packaged executable. Codex's
own probes under `test/audit-rdna2-2026-11-11/` were not rerun. Access failures
were only produced with permissions on synthetic trees; errors other than
EACCES and ENOENT were not produced.


## Independent verification of fixes 15 and 16 (2026-11-11, Codex)

Audited htop `7c2fe84b07755eb1743ce6d5ef5517a96ad8bdda`, outer `d4db927`,
patches 0001–0014 and installed package 3.5.3-15. Compared the fix to `f842f486`
and reviewed the eight added assertions. **Findings 15 and 16 are confirmed
fixed; no new actionable findings.**

### Recovery and regression-test verification

- Reran the original independent probes from the preceding audit, copied to a
  fresh folder. After the sensor directory is unsearchable for six refreshes,
  restoring permissions now restores all temperatures, both clocks and fanMax
  in the same process. The file-level permission control still passes.
- The original clock probe now moves from a temporary 600 MHz scale to the
  recovered 2575 MHz maximum on the very next refresh and keeps that scale for
  all eight subsequent samples. All nine GC variants still discover correctly
  with a missing ids file and their chip-name fallbacks.
- Ran the current committed fake sampler tests against an isolated copy of
  `f842f486` (only the build input was changed; the live phase was omitted).
  Exactly the two intended assertions fail: sensor recovery after six denied
  refreshes, and clock-scale recovery to 2575 MHz. All other fake assertions
  pass. This independently confirms the new tests reject the buggy source.
- Additional ASan/UBSan probes exercised ELOOP for fan1_max, freq1_label and
  pp_dpm_sclk, and ENOTDIR for the sensor directory. Each recovered in the same
  process after nine failed refreshes. These validate error types beyond
  Claude's EACCES and ENOENT cases.
- VCN probe: a looping attribute symlink reports unavailable, removing it
  enables the 37% gpu_metrics fallback, and creating a readable direct
  attribute changes the result to its 55%. Error and absence stay distinct.
- A delayed DPM maximum recovered across synthetic suspend/resume without
  shrinking a previously observed 2700 MHz peak. Unbinding and rebinding a
  different GC variant reset the cached seed to that card's 1800 MHz maximum.
  All independent probes exited cleanly with no sanitizer reports.

### Build, release and installed checks

- Build passed without warning/error diagnostics; style reported STYLE OK.
  The complete sampler suite passed all 169 assertions, including the live
  VA-API workload (100% video load observed). Heading tests passed all 25
  assertions, including the full-program sanitizer checks and live headings.
- All 14 patch checksums match PKGBUILD. The series applies to tag 3.5.3 without
  fuzz or offsets and reproduces all 16 changed source files at HEAD exactly.
  Patches 0001–0013 differ from the preceding release only in subject numbering.
- Archive SHA-256 is
  `bcbd15105e4e55688079187203ac47b57d649f81cc008ae765cfba7470cea077`.
  All five installed payload files match the package archive; pacman reports
  zero altered files. The installed executable reports `3.5.3-15-gpu` and
  displays the RX 9070 XT heading and AMD readings in a throwaway config.

Evidence is in ignored `test/audit-fixes15-16-2026-11-11/`, including the original
probes, extra probes, isolated negative control, patch proof and all test logs.
Only AUDIT.md, CHANGELOG.md and PLAN.md changed, left uncommitted. No source,
committed test or package edits; no install, commit or push. Hardware testing
remains limited to the RX 9070 XT. Other cards, access failures, sleep and card
replacement were simulated; real firmware errors, suspend and hotplug were not
exercised. Unchanged kernel-layout/card-table assumptions retain the previous
audit's verification; no new kernel research was necessary for this fix.


## Full project audit (2026-11-11, Codex)

### Scope and result

Reviewed all 14 custom commits above htop 3.5.3 at source
`7c2fe84b07755eb1743ce6d5ef5517a96ad8bdda`, outer `d4db927`, and installed
3.5.3-15. Scope includes all 16 changed source files (AMD, Intel GPU, CPU power,
headings, config isolation and registration), test/build/release helpers,
PKGBUILD/patches, current README and plan claims. The preceding fix-verification
records were already uncommitted and are preserved.

Three actionable findings: 17 (P2, runtime power-state handling), 18 (P3, update
checker), 19 (P3, documentation). No fixes were applied. Previously fixed
findings 15/16 remain verified; deferred finding 7 (additional RAPL packages)
and accepted finding 12 (CPU-name UTF-8 truncation) retain their prior status.

### 17. [P2] AMD samples hardware when runtime state is unknown or transitioning

Location: `src/htop/linux/AMDGPU.c:470-476`.

Only a successfully read exact `suspended` string stops dynamic reads. A failed
runtime_status read, `suspending`, or `resuming` falls through to AMDGPU_ACTIVE
and reads the hardware attributes. This violates the intended passive-monitoring
behavior when an AMD card is entering sleep or its state cannot be established.
IntelGPU_refresh already avoids analogous unknown/transition-state reads.

Reproduced under one running ASan/UBSan sampler for each state: first establish
an active baseline, replace the copied gpu_busy_percent attribute with a blocking
FIFO, then change runtime_status. Exact `suspended` returns immediately without
opening the FIFO. `suspending`, `resuming`, a missing status file and an unreadable
status file all attempt the dynamic read and wait for a writer. Supplying `7`
unblocks them, producing status `active` and gpuBusy 7; restoring the tree then
recovers normally. The permission-denied case's actual status contents remain
`suspended`, so treating an unreadable status as awake is directly demonstrated.
All probe processes exit cleanly after the controlled FIFO release.

Hardware consequence is kernel-dependent: in
[Linux v6.12 amdgpu_pm.c](https://github.com/torvalds/linux/blob/v6.12/drivers/gpu/drm/amd/pm/amdgpu_pm.c),
gpu_busy_percent calls amdgpu_hwmon_get_sensor_generic, which uses
pm_runtime_get_sync and can resume a runtime-suspended device. This matters to
supported RDNA 2/3 systems on such kernels. The v7.3 source examined in the
preceding audit uses get-if-active reads instead, mitigating the wake consequence;
this machine also has runpm disabled. No physical wake was induced or measured.
This is an existing sampler behavior exposed by the broader review, not a
regression introduced by the findings 15/16 fixes.

Suggested correction: stop hardware sampling on read errors and sleep
transitions, retain metadata, and report unavailable/sleep until the card is
known active. Define an explicit policy for kernels without runtime-PM support.
Add stateful FIFO guards for failed status reads and transitions, in addition
to the existing exact-suspended case. An active-to-sleep race after a successful
state read is a separate driver-level limit, not solved by this guard alone.

Evidence: `test/full-audit-2026-11-11/amd-power-state.py`, its `.log`, and
`amdgpu_pm-v6.12.c`.

### 18. [P3] Upstream checker requires an undocumented developer checkout

Location: `tools/check-upstream.sh:7-15`; README's installation/update instructions.

The README installs from the outer project repository with makepkg, then directs
the user to check-upstream.sh for new releases. The script instead queries the
`upstream` remote in `src/htop`, a separate ignored developer clone. A documented
fresh installation does not create that path: makepkg's checkout is under
packaging. As a result the advertised checker cannot determine an upstream
version, even if network access is available.

Reproduced in a temporary git repository containing the committed helper and
PKGBUILD, with no developer src/htop clone. The helper exits 1 and prints
`upstream latest tag: unknown (no network?)`. The local repository/remote lookup
fails before an official upstream URL can be queried; the message misleadingly
suggests network trouble.

Suggested correction: query the official htop URL directly, or use the developer
remote only when it exists and fall back to the URL. Add a lightweight isolated
helper test that does not provide src/htop. The script's old comment saying this
package replaces stock htop should also be updated when touching the file.
Evidence: `fresh-project/` and `fresh-upstream-check.log` in the audit directory.

### 19. [P3] Display-mode documentation omits the Intel memory restriction

Locations: `README.md:54`, `PLAN.md` Meters paragraph (around line 144 before
this audit's status addition). `src/htop/linux/IntelGPUMeter.c:183-198` is the
reference implementation.

The docs say every non-heading meter supports bar, text, graph and LED modes.
IntelGPUMemory explicitly supports only text and LED, because it has no meaningful
whole-device memory denominator. Users cannot select the advertised bar/graph
modes for that meter. The prior finding 9 correction added the heading exception
but left this other exception unmentioned.

Suggested correction: document Intel iGPU memory as text/LED only in both places;
keep the implementation's deliberate restriction. Confirmed by the class's
supportedModes declaration and sanitized text/LED captures; no runtime change
is needed.

### Validation

All checks below passed. Existing suites do not cover finding 17's failing state
reads/transitions or finding 18's fresh-install layout.

| Area | Evidence |
| --- | --- |
| AMD sampler | 169 assertions, including live encode, from the preceding same-version audit |
| Headings | 25 assertions from the preceding same-version audit |
| Config isolation | 33 assertions on the dev binary and 33 on installed /usr/bin/htop-gpu |
| Style gate | 7 checks, including broken-tool and deliberately bad-style controls |
| CPU power | 49 assertions; live idle 9.34 W, busy 126.82 W; sanitizers clean |
| Intel GPU | 158 assertions, including three negative controls and live encode/decode/graphics; peaks 32.9%/18.7%/100% |
| Full sanitizer build | All source files instrumented; normal build restored afterward; no new warnings |
| Meter modes | Twelve numeric meters exercised in all four modes, all three headings in text, Intel memory in text/LED; no sanitizer reports |
| Static analysis | GCC -fanalyzer on all six custom implementation .c files: no diagnostics |
| Tool syntax | Every Python helper parsed; bash -n passed for all shell helpers and PKGBUILD |

The source and package did not change between the immediately preceding audit
and this one, so its successful build/style, AMD/heading suites, error-recovery
probes, old-source negative control and 14-patch checksum/application proof are
retained instead of redundantly rerunning them. Logs remain in
`test/audit-fixes15-16-2026-11-11/`. That proof reproduces all 16 changed source
files exactly from upstream tag 3.5.3. This audit's full sanitized and normal
rebuilds additionally compile the entire current development source.

Rechecked the package archive SHA-256
`bcbd15105e4e55688079187203ac47b57d649f81cc008ae765cfba7470cea077`, all five
installed payload files against it, and pacman integrity (zero altered files).
No payload paths collide with stock htop. Versions remain htop-gpu 3.5.3-15 and
stock htop 3.5.3-1.1. The normal dev executable contains neither ASan nor this
audit's fake path. namcap still reports the established hicolor-icon-theme,
implicit glibc and possibly unnecessary libnl diagnostics; no new diagnostic.

### Limits and preservation

Evidence and reproducible probes are in ignored `test/full-audit-2026-11-11/`.
The FIFO proves a read attempt, not an actual hardware wake or kernel hang.
Hardware testing is limited to this RX 9070 XT, Arrow Lake iGPU and CPU. Other
AMD generations, errors and transitions were simulated; no physical hotplug,
forced suspend or external Mission Center comparison. UI captures exercise
supported modes but are not an interactive walkthrough of every F2 operation.
No package rebuild/install or dependency change was performed. Review covers
the project's changes and their integration, not an exhaustive independent
review of every unchanged upstream htop file or external dependency.

Only AUDIT.md, CHANGELOG.md and PLAN.md are modified, including the earlier
uncommitted fix-verification records. No runtime/source/test fixes, no commit or
push, and no real config/sysfs permission changes. The source worktree is clean.


## Resolution of findings 17, 18 and 19 (2026-11-11, Claude Code)

Claude Code (Claude Fable 5.2). 17 and 18 were reproduced first as new tests
against the audited code (htop `7c2fe84b`, outer `d4db927`): the sampler read the
FIFO in every state but an exact `suspended` (14 failed checks), and the old
checker failed 5 of the 6 new checker checks.

- **17, fixed** in `linux/AMDGPU.c` / `.h`. New `AMDGPU_powerState()` with an
  explicit policy, and a new status `AMDGPU_UNAVAILABLE` (found, nothing read):
  - read the card: `runtime_status` is `active`; or `unsupported` (runtime power
    management not in use for the device); or the file is confirmed absent
    (ENOENT, a kernel without runtime PM). This is the "kernels without
    runtime-PM" policy the audit asked for.
  - `AMDGPU_SUSPENDED` ("sleep"): `suspended`, `suspending`, `resuming`.
  - `AMDGPU_UNAVAILABLE` ("N/A", card name and one-time values kept): `error`,
    any other text, an empty file, or a read that fails for any reason but
    ENOENT.
  The meter file needed no change: it already shows N/A for every status that is
  neither active nor suspended, and the heading reads `<card>: N/A`.
  Differs from the Intel iGPU sampler in two deliberate ways: `resuming` is
  shown as sleep rather than unavailable, and `unsupported` / no file count as
  awake. The race the audit names (card suspends after the status was read)
  is not addressed.
- **18, fixed** in `tools/check-upstream.sh`: it asks `src/htop`'s `upstream`
  remote when that clone has one, otherwise `https://github.com/htop-dev/htop.git`
  (`HTOP_UPSTREAM_URL` overrides, used by the test). On failure it says where it
  asked. The stale "replaces the repo htop" comment is corrected. New
  `tools/test-check-upstream.sh` (6 checks, local stand-in repositories).
- **19, fixed** in README.md and the PLAN.md Meters paragraph: `IntelGPUMemory`
  is text / LED only. No code change.

New tests: `test-sampler.py` +29 (198): first-sample cases for `unsupported`,
`suspending`, `error`; under one running sampler with `gpu_busy_percent` as a
FIFO, the states suspended, suspending, resuming, error, unknown text, empty and
unreadable must not attempt a read, must keep card and one-time values, and
must read everything again once active. `test-headings.py` +2 (27): unknown
power state under one running htop.

Validation: build without warnings, `STYLE OK`, `test-sampler.py` ALL PASSED
(198, live idle + VA-API encode, ASan/UBSan), `test-headings.py` ALL PASSED (27),
`test-check-upstream.sh` ALL PASSED (6), and a real `check-upstream.sh` run
against the developer clone (3.5.3, up to date).

Released the same day at the user's request: htop `943464c0` (patch 0015),
package 3.5.3-16, SHA-256
`882e5f46cbacb36d3f9966f71ea9ae891c2401122231603a856ebd9d5b9ea580`. Patches
0001-0014 only change their `[PATCH nn/15]` numbering; namcap gives the same
three diagnostics. Installed with `pacman -U`: `pacman -Q` reports 3.5.3-16,
`/usr/bin/htop-gpu` matches the package executable byte for byte and shows
`Radeon RX 9070 XT` with all AMD meters live in a throwaway config.

Limits: the suites ran on the development tree, not the packaged executable.
Codex's probes under `test/full-audit-2026-11-11/` were not
rerun. The FIFO shows read attempts, not hardware wakes; no real suspend. The
GitHub URL fallback was not exercised over the network (the real run used the
clone's remote). RAPL, Intel GPU, config and style-gate suites were not rerun:
their sources are untouched.


## Independent verification of fixes 17–19 (2026-11-11, Codex)

Reviewed source `943464c03fa21d89440cac37cbc4b4a90c01150a`, outer `bc4e168`,
patches 0001–0015, updated tests/docs and installed package 3.5.3-16.
**Findings 17, 18 and 19 are confirmed resolved under the documented power-state
compatibility policy. No new actionable findings.**

### Independent reproductions and controls

- Reran the original stateful FIFO reproduction from the full audit in a new
  directory. Exact suspended, suspending and resuming now avoid dynamic reads;
  an unreadable runtime_status returns unavailable and also avoids the read.
  Each recovers when active returns, with no sanitizer report.
- A confirmed missing runtime_status file still permits sampling. This is the
  explicit policy for kernels without runtime PM, alongside the literal
  unsupported state; it is not an unaddressed read-error case. The missing-file
  reproduction accordingly still reports active and attempts the read. The
  implementation does not distinguish a genuinely unsupported interface from
  an interface hidden by a custom sysfs mount. Its active-to-sleep race also
  remains the documented limitation.
- Added independent first-sample FIFO guards on pp_dpm_mclk: error text, an
  ELOOP status symlink and a denied power directory all avoid static-value reads
  before initialization. All recover when active returns. Unsupported permits
  sampling as documented. These probes exit cleanly under ASan/UBSan.
- Ran isolated copies of the current fake sampler tests against the prior
  `7c2fe84b` sampler (current enum header/test driver, old implementation; live
  phase omitted). Exactly 14 assertions fail, all associated with the old
  power-state behavior. The other fake assertions pass.
- Current update-checker tests pass all six local-repository checks. Against
  the previous helper at `d4db927`, five assertions fail as expected. Separately,
  a temporary outer checkout layout with no src/htop and no URL override queried
  the official GitHub repository successfully: exit 0, latest tag 3.5.3. This
  exercises the real network fallback omitted from Claude's validation.
- README and PLAN now both describe Intel memory as text/LED only, consistent
  with IntelGPUMemoryMeter_class. The existing heading exceptions are retained.

### Validation and installed release

Build completed without warning/error diagnostics; style reported STYLE OK.
All 198 sampler, 27 heading and six checker assertions passed (231 total),
including live AMD encode at 100% video load and the heading suite's sanitizer
checks. The normal development executable was restored and verified by the
heading suite. Unchanged RAPL, Intel GPU, config and style-gate results from the
preceding full audit remain applicable; those suites were not redundantly rerun.

All 15 patch checksums match PKGBUILD. Applying the series to tag 3.5.3 succeeds
without fuzz/offsets and reproduces all 16 changed source files exactly. Earlier
patches 0001–0014 changed only their subject numbering. Archive SHA-256:
`882e5f46cbacb36d3f9966f71ea9ae891c2401122231603a856ebd9d5b9ea580`.
All five installed payload files match the archive, pacman reports zero altered
files, and the installed executable reports `3.5.3-16-gpu`. A throwaway-config
capture shows the RX 9070 XT heading and AMD readings.

Evidence, isolated negative controls, original/extra reproductions and package
proof are in ignored `test/audit-fixes17-19-2026-11-11/`. Only AUDIT.md,
CHANGELOG.md and PLAN.md changed, left uncommitted. No source/committed-test
changes, package rebuild, installation, commit or push. No real sysfs permissions
or user configs changed. FIFO guards prove skipped reads rather than physical
power behavior. No real suspend/hotplug or other AMD hardware was tested.
