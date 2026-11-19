# Intel iGPU: secondary implementation plan

Created: 2026-10-28. Updated: 2026-10-29 (America/Phoenix). Author: Codex.
Status: baseline implemented, tested, and installed as htop-gpu 3.5.3-12.
Committed 2026-10-29 after Claude Code's review: source `bb4f7331`, tests/docs/packaging in the outer repo.
Finding 8 (P2) is fixed and validated in 3.5.3-12: lost access to a known Intel
client reports unavailable instead of false zero. See AUDIT.md.
Revised plan committed and pushed first as outer `b145c766` at the user's request.
The user's third column now places the Intel block beneath the eight AMD meters;
the original config was backed up. See the release record below.
This supplements PLAN.md and follows AGENTS.md.
The user wants Intel iGPU stats below the RX 9070 XT stats in the existing third column.
The user selected Mission Center's utilization, clock speed, memory usage, and video encode/decode as the initial baseline, and requested a plan update before implementation.

## Compatibility update (2026-11-19)

The local source and 3.5.3-17 package recipe extend the original single-device baseline to the Tiger Lake, Rocket Lake, Alder Lake and later integrated families listed in the README. The sampler uses the bound driver and PCI identity. On i915 it reads engine time and allocated system0 bytes. On xe it compares busy and total GPU cycle deltas and sums the separate system and GTT allocation totals. It finds the graphics GT by render or compute engine class. A GPU exposing only one of those classes can supply utilization from that class. The release records below describe the original i915 implementation. See AUDIT.md for verification and hardware coverage.

## Recommended approach

Add an independent Intel sampler and meters, starting with the currently bound i915 driver.
Use readable DRM client counters for activity and allocated memory, and sysfs for the selected clock reading.
Describe activity as covering visible applications, rather than promising device-wide coverage.
Device-wide PMU access is currently denied to the normal user; treat it as an optional later backend.
Keep the existing AMD meters and CPU package-power meter intact.

The initial block should show one utilization meter, one clock readout, one shared-memory usage readout, and one combined video encode/decode meter.
Keep render/compute details in the sampler, but defer separate compute, copy, enhancement, and media-clock rows.
Do not add placeholder power, temperature, fan, or dedicated-VRAM bars for sources this machine does not expose.
Memory usage is part of the first version; only an exact global physical-memory total/percentage remains outside the baseline.

## Confirmed machine and software

| Item | Observed value |
| --- | --- |
| CPU | Intel Core Ultra 7 270K Plus, confirmed by `/proc/cpuinfo` |
| Intel GPU | Arrow Lake-S / Intel Graphics, PCI `8086:7d67`, revision `06` |
| Intel PCI address | `0000:00:02.0` |
| Bound driver | `i915`; xe is listed as an available module, not the driver in use |
| Intel nodes this boot | `card1`, `renderD128` |
| Stable Intel render path | `/dev/dri/by-path/pci-0000:00:02.0-render` |
| AMD GPU | RX 9070 XT, `1002:7550`, `0000:04:00.0`, amdgpu |
| AMD nodes this boot | `card2`, `renderD129` |
| Kernel | `7.3.0-4-cachyos` |
| Installed project | `htop-gpu 3.5.3-8` |
| Outer baseline, initial investigation | `8601dca3e9715af70a099d40b1a707ea63766e93` |
| Outer baseline, Mission Center refinement | `51c64de5305ece34a6d67c3fcced9c1d78bf4e11` |
| htop source baseline | `61c598b1a128e06864a4f071347d6ed63ce71282` |

Discover the PCI device and its associated DRM nodes dynamically; these card/render numbers are observations, not constants to put in code.
Scope initial support to this Intel PCI ID and i915, with a small explicit device table.
Select deterministically if multiple supported devices are present, and never aggregate the AMD device into Intel statistics.
If xe becomes bound later, show unsupported/unavailable until an explicitly implemented xe backend is available.
Do not switch drivers as part of this feature.

## Interfaces checked on this host

### Activity without additional privileges

Readable `/proc/<pid>/fdinfo/<fd>` entries contain:

- `drm-driver: i915`, `drm-pdev: 0000:00:02.0`, and `drm-client-id`.
- `drm-engine-render`, `compute`, `copy`, `video`, and `video-enhance`, in nanoseconds.
- `drm-engine-capacity-video: 2`; absence of a capacity key means one engine.
- Memory categories including `drm-resident-system0`, `drm-shared-system0`, and `drm-total-system0`.

An inventory found ten distinct readable Intel clients after deduplicating PCI address/client ID.
Some process fdinfo directories cannot be inspected by this user; this is not proof those processes use the GPU.
Therefore the result is activity attributable to visible clients, with possible omissions from other or short-lived clients.
Meter descriptions communicate that scope. At the user's request, the normal
heading is just `Intel iGPU`; sleep and access/error indications remain visible.

The [DRM usage-statistics specification](https://docs.kernel.org/gpu/drm-usage-stats.html) defines client identity, engine capacities, counter behavior, and memory categories.
The [i915 implementation](https://raw.githubusercontent.com/torvalds/linux/v7.3/drivers/gpu/drm/i915/i915_drm_client.c) confirms accounting per engine class.

### Clock sources

Use `/sys/class/drm/<Intel card>/gt/gt*/`, rather than the legacy card-wide frequency aliases.
The latter cannot express both domains clearly.

| Attribute | GT0 observed | GT1 observed | Meaning in the proposed UI |
| --- | --- | --- | --- |
| `rps_act_freq_mhz` | 0 MHz in sampled idle/media intervals | 0 or 500 MHz | Actual render / media clocks; optional later details |
| `rps_cur_freq_mhz` | 0 MHz when sampled idle | 0 MHz when sampled idle | Requested render clock selected for the Mission Center baseline |
| `rps_min_freq_mhz` | 550 MHz | 100 MHz | Configured minimum request |
| `rps_max_freq_mhz` | 2000 MHz | 1400 MHz | Current configured maximum request |
| `rps_RP0_freq_mhz` | 2000 MHz | 1400 MHz | Hardware maximum exposed here |

GT1 reaching 500 MHz during the pinned video workload supports its media-domain identification on this host.
The implementation's pinned Vulkan workload subsequently verified render activity
and a 2000 MHz requested GT0 clock; see the implementation record below.
Retain per-device GT mapping explicitly; do not generalize these IDs to every Intel GPU.
Zero actual frequency is a reported value, even when the device runtime state is active.
Missing/unreadable values are unavailable, not zero.
Mission Center's pinned Intel backend uses the card-wide requested `gt_cur_freq_mhz` value.
For baseline parity, use the equivalent GT0 requested value and identify it as
requested in the meter description. The compact header omits that qualifier
at the user's request; this does not change the underlying clock source.
Do not silently switch between requested and actual readings when a source is unavailable.
Configured limits may change; reread mutable limits on newer ticks, preserving the PL1 audit lesson.
The [i915 GT sysfs implementation](https://raw.githubusercontent.com/torvalds/linux/v7.3/drivers/gpu/drm/i915/gt/intel_gt_sysfs_pm.c) separates actual and requested frequency reads.

### Device-wide counters: optional, blocked for this user today

`/sys/bus/event_source/devices/i915` exists with PMU type 16 and CPU mask 0 on this boot.
It exports busy events for rcs0, ccs0, bcs0, vcs0, vcs1, and vecs0, plus per-GT frequency events.
A temporary normal-user `perf_event_open` probe for rcs0-busy returned `EACCES` (errno 13).
`kernel.perf_event_paranoid` is 2, despite read/write access to the Intel DRM nodes.
DRM-node permissions alone therefore do not solve the PMU access problem.

Do not require running htop as root, changing sysctls, or granting broad capabilities for the initial implementation.
An optional PMU backend would require a separately considered access mechanism, with real-host validation and a clear fallback.
Do not claim that granting CAP_PERFMON alone is sufficient on this driver until tested.
See [Linux perf access controls](https://docs.kernel.org/admin-guide/perf-security.html).

### Sensor limits and memory semantics

No hwmon directory was found under this Intel PCI device, so no usable iGPU temperature or direct power sensor was established.
RAPL exposes package-0, core, and uncore; only package energy is readable with the existing rule.
The uncore counter is unreadable and has not been validated as an isolated graphics-power measurement on this platform.
Do not reuse CPU package watts or temperature as iGPU watts or temperature.

The iGPU's client memory categories describe shared-system-memory allocations, not a discrete card's dedicated VRAM pool.
Include a text readout of visible-client allocated bytes in the first version, using `drm-total-system0` for the current host, as Mission Center's fallback does.
Do not silently replace allocated bytes with resident bytes; they can differ even though this investigation's snapshots happened to match.
Shared buffers may appear in multiple distinct clients, so show an approximation marker and document that scope.
Deduplicate client identities, but do not claim that this also deduplicates buffer objects across clients.
Defer only a unique global-memory percentage/bar until its numerator, denominator, and sharing policy are defensible.
Do not invent a VRAM capacity, use all system RAM as a fake VRAM limit, or apply the RX 9070 XT's GDDR6 clock conversion.
There is no separate iGPU fan sensor in this inventory.

## Mission Center reference checked on 2026-10-29

Installed Mission Center is `1.2.0-1.1`.
Inspected its official `v1.2.0` release, commit `193e3729367035cf184da004c3246efe79d5c53e`, without launching or changing the application.
That release pins Magpie `a5272b3c1d853caa4044b737cf49257bfc4c86f2`, which in turn pins NVTOP `3d4a953da02bc18886734613bb9f60ff80669de7`.

- **Utilization:** the pinned Intel backend derives a visible-client graphics-work estimate from render and compute accounting; the device summary sums process estimates and caps the display at 100%.
  This is not a measured union of all GPU-engine busy intervals.
  Adopt that documented graphics-work proxy for the baseline, retain raw class deltas, and improve descriptor/client deduplication rather than copying implementation quirks.
- **Clock:** its Intel path reads requested `gt_cur_freq_mhz`, rather than actual `gt_act_freq_mhz`.
  Matching that source avoids comparing two different frequency concepts under the same label.
- **Memory:** it tries an i915 memory-region query, with per-process allocated-memory accounting as a fallback when an actual used/free value is unavailable.
  Its i915 parser uses `drm-total-system0` (and local memory where present), not resident memory.
- **Video:** Intel is marked encode/decode-shared; both internal rates originate from the same video counter, and the UI labels the shared case as video encode/decode.
  Use one E/D meter, not duplicate encode/decode bars pretending to be independent.

Sources: [Mission Center UI at v1.2.0](https://gitlab.com/mission-center-devs/mission-center/-/blob/v1.2.0/src/performance_page/gpu.rs),
[its pinned Magpie integration](https://gitlab.com/mission-center-devs/gng/-/blob/a5272b3c1d853caa4044b737cf49257bfc4c86f2/platform-linux/src/gpus/mod.rs),
[pinned NVTOP Intel frontend](https://raw.githubusercontent.com/Syllo/nvtop/3d4a953da02bc18886734613bb9f60ff80669de7/src/extract_gpuinfo_intel.c),
[i915 accounting](https://raw.githubusercontent.com/Syllo/nvtop/3d4a953da02bc18886734613bb9f60ff80669de7/src/extract_gpuinfo_intel_i915.c),
and [device-summary aggregation](https://raw.githubusercontent.com/Syllo/nvtop/3d4a953da02bc18886734613bb9f60ff80669de7/src/extract_gpuinfo.c).

### Additional memory proof

A normal-user `DRM_IOCTL_I915_QUERY` memory-region query succeeded on the Intel render node.
It returned one system-memory region, with both probed and unallocated fields equal to 66,628,472,832 bytes.
That equality does not establish zero iGPU memory usage: the driver can withhold a meaningful unallocated value without elevated monitoring access.
Do not calculate used bytes as zero from that result.

A separate same-scan snapshot found nine unique readable Intel clients with 218,872 KiB allocated in system memory, also 218,872 KiB resident in that snapshot, and 24,584 KiB marked shared.
The shared count is a category within the allocation, not an extra amount to add on top.
This is evidence for a useful initial memory readout, not proof of unique physical bytes across all clients.
The default text is `iGPU mem: 214M`; keep the approximate allocated-memory and
visibility explanation in the meter descriptions.
The system-region budget may be shown later only if explicitly labeled as shared capacity, never dedicated VRAM.
An optional query must open only while the device is already active and close promptly; the text-first baseline need not query every tick or add a libdrm runtime dependency.

## Live proof completed

A six-second, 1080p60 H.264 VA-API encode was pinned to the Intel render path and wrote to the null muxer.
It exited 0 with no error output and created no video file.
Ten snapshots identified one Intel client, capacity two for video, and 82,544 KiB of resident system memory for that client.
Across approximately 4.507 seconds of sampled intervals, its video counter increased by 1,330,747,548 ns.
That is about 14.76% averaged across both video engines for the sampled interval, not 14.76% render utilization.
The Mission Center-style busy-time convention would show about 29.52% before display saturation for that same interval, because it does not divide by the video capacity of two.
For the baseline, document this convention and cap only the displayed E/D activity index at 100%; retain capacity and raw deltas for validation.
Do not call that index the percentage of all available video-engine capacity.
GT0 remained 0 MHz in those snapshots; GT1 was observed at 500 MHz during part of the workload.
This validates the video-counter path; it does not validate render, compute, copy, enhancement load, or video decode.

Device runtime state was seen both suspended and active during the investigation.
The cause of changes outside the explicit workload was not isolated.
A passive monitoring loop must be tested to ensure it does not keep the iGPU awake.

## Proposed position and meter names

Keep `header_layout=three_33_34_33` and append to `column_meters_2`, after the existing eight AMD meters.
The current left and middle columns each have sixteen meter rows.
The narrower baseline uses fourteen rows in the right column at the default modes, subject to a real terminal check:

```text
GPU usage                 existing RX 9070 XT rows 1–8
VRAM
Pwr
VCN
Fan
GPU temp
GPU clock
VRAM clock
                          Blank
Intel iGPU                new text heading
iGP [utilization]
iGPU clock: ...MHz
iGPU mem: ...M
Vid [video encode/decode]
```

| Internal name proposed | Caption | Default mode | Source |
| --- | --- | --- | --- |
| `IntelGPUInfo` | `Intel iGPU` | Text | Device heading, sleep/access/error status |
| `IntelGPUUsage` | `iGP` | Bar | visible-client render/compute graphics-work estimate |
| `IntelGPUClock` | `iGPU clock: ` | Text | Requested GT0 clock, matching the reference source |
| `IntelGPUMemory` | `iGPU mem: ` | Text | approximate visible-client allocated system bytes |
| `IntelGPUVideo` | `Vid` | Bar | combined encode/decode video activity |

These names are supported by both the development and installed 3.5.3-12 binaries.
Keep class counters separate internally and use an explicit summary rule for the single utilization bar.
For the selected reference-style graphics-work proxy, sum valid render/compute contributions and saturate the displayed index at 100%; do not add video/copy/enhancement to that total.
Retain unsaturated values and coverage state so valid overlap is distinguishable from corrupt counters.
Clock charts use the requested render clock against its current configured maximum.
Memory remains useful in text/absolute-byte forms when a trustworthy bar denominator is unavailable; a missing total must not hide valid allocated bytes.
The text heading is informational; utilization and video meters need all four normal display modes.
Placement changes happen only after implementation passes, with a backup and no htop-gpu process running while its real config is edited.
A disposable copy at `test/intel-igpu-preview.rc` now demonstrates this layout;
the user's saved layout now uses the same Intel placement after the authorized release.

## Sampler design

Add `linux/IntelGPU.{c,h}` and `linux/IntelGPUMeter.{c,h}`.
Only registration/include lines should touch upstream `Makefile.am` and `linux/Platform.c`.
Preserve upstream `linux/GPU.c`, the stock GPU header meter, and GPU process columns.
The current stock accumulator groups engine data without a device key, so it cannot directly supply an Intel-only header block.

1. Discover a supported Intel PCI graphics device, its i915 binding, DRM card, GTs, and stable identity.
   Retry incomplete discovery and invalidate stale paths after removal or renumbering.
2. Check runtime state before reading dynamic hardware attributes.
   While suspended, show sleep, skip clock/PMU work, and rebaseline activity on wake.
   Avoid permanently opening an Intel render node just to monitor it.
3. Scan eligible process fdinfo once per newer htop tick, shared by every Intel meter.
   Filter driver and PCI address, then deduplicate `(PCI address, drm-client-id)` globally across processes and descriptors.
   Do not key only by PID, descriptor number, engine name, or client ID alone.
4. Keep per-client/per-engine history with actual elapsed monotonic time.
   Compute raw busy-time ratios for each class; also retain capacity-normalized values for validation and optional future class displays.
   Do not sum capacity once per client; capacity two describes the device's video-engine group.
   Missing capacity defaults to one; reject zero, malformed, or conflicting capacity reports.
   Build the visible-client utilization and combined E/D summary using the documented reference conventions above.
   Display saturation is intentional for these proxy indexes; do not reject a valid dual-video-engine delta merely because it exceeds one wall-clock interval.
5. Baseline newly seen clients; do not count their lifetime history as activity in the current tick.
   Keep a counter high-water mark on temporary backward reports, as specified by the DRM ABI.
   Confirmed device reset/removal establishes a new generation and fresh histories.
   Client exit, PID/FD reuse, skipped/inaccessible reads, and changing client sets must not cause negative values or spikes.
6. Represent validity and visibility separately from percentages.
   A partial visible-client result must not be labeled device-wide.
   First samples and insufficient history are unavailable; valid idle deltas are zero.
   Validate raw deltas independently rather than letting intentional display saturation conceal accounting errors.
7. Select the requested render clock explicitly for the baseline, retain the distinction from actual clocks, and refresh mutable scaling values.
   One successful read must not prevent future read failures and recovery from being observed.
8. Sum valid allocated-byte fields once per visible client, with checked unit conversion and a clear approximation/coverage status.
   Keep allocated, resident, and shared categories separate; never add shared bytes to a total that already includes them.
   Handle missing individual fields and inaccessible clients without manufacturing a whole-device zero or losing valid known byte counts.
9. Cache the entire result for same/older `host->monotonicMs` calls.
   Release transient resources and bound history storage; expire stale clients without losing correctness across brief access gaps.

An optional later PMU backend should report its device-wide scope explicitly, rebaseline on backend switches, and preserve the unprivileged fallback.
Derive PMU event type, CPU mask, and event configs dynamically rather than copying this boot's numbers.

## Implementation stages and acceptance

1. **Standalone probe and fixtures.**
   Add a small `tools/intel-gpu-sample.c` driver, fake sysfs/proc roots, and `tools/test-intel-gpu.py`.
   First prove scanner semantics, the utilization summary, allocated memory, requested clock validity, combined video activity, and failure/recovery without touching htop's UI.
   Use measured ABI examples; store sanitized fixture data rather than live PIDs or unrelated process contents.
2. **Read-only sampler.**
   Implement i915 discovery, per-tick caching, sleep handling, per-client deltas, raw/capacity-aware accounting, allocated memory, and the requested clock.
   Benchmark scan cost and idle CPU overhead against stock htop and the existing build before optimizing.
   Do not require a new runtime command, daemon, package, or privileged htop process.
3. **Meters and disposable layout.**
   Add the heading and four baseline meters; reuse existing htop colors and display machinery.
   Verify the compact fourteen-row block in the third column with both AMD and Intel enabled.
4. **Live validation.**
   Repeat the pinned Intel encode, add Intel decode and render/compute workloads, and confirm the single E/D meter responds to both media operations.
   Validate requested clock changes, allocated-memory growth/release, transitions back to idle, and suspend/wake without monitoring-induced wakeups.
   Compare side by side with installed Mission Center 1.2.0, checking source/visibility, allocated versus resident bytes, and video denominator conventions before expecting numeric parity.
   The reference application is not a production dependency.
5. **Release and placement.**
   Run required existing suites, new Intel tests, style, full sanitized meter checks, packaging diagnostics, and config-path checks.
   Commit/export patches, bump pkgrel, build and verify the package, then install and append the block to the user's backed-up layout when that implementation/release work is requested.
   Record all validation in AUDIT.md and finish the shared handoff in PLAN.md/CHANGELOG.md.

Required stateful regression cases include mixed Intel/AMD clients; duplicate descriptors and shared/forked clients; reused IDs and process exit; render/compute summary with valid overlap; combined encode/decode aliases; video capacities one/two/malformed and dual-engine activity above one engine-equivalent; allocated/resident/shared differences; units and overflow; memory growth/release; unavailable totals with valid used bytes; first sample; same/older ticks; partial access; disappearing files; temporary backward counters; device reset; node/GT renumbering; zero clocks; requested versus actual values; late/mutable limits; and sleep/wake.
Use the same running sampler across transitions, and include negative controls that deliberately break device filtering, deduplication, and capacity normalization.
Run new sampler tests under ASan/UBSan and verify actual meter displays and totals, not only JSON results.

## Open decisions and limits

The initial recommendation is the unprivileged visible-app backend, with no permission changes.
Memory usage is required in the initial baseline; exact unique global-memory totals remain a separate problem, not a reason to omit the basic readout.
Device-wide PMU access, isolated iGPU power, and temperature require separate investigation or approval where system access changes are involved.
Separate engine bars and actual/media-clock details are deferred until after the four-stat baseline.
Initial GT mapping is host-specific; xe and other Intel PCI IDs are future work.
Additional CPU-package discovery from AUDIT.md finding 7 remains deferred and is unrelated to this plan.

The initial investigation and plan refinement did not modify production code or
installation. The subsequent implementation is recorded below.

## Implementation record: 2026-10-29

Added `linux/IntelGPU.{c,h}` and `linux/IntelGPUMeter.{c,h}` in the nested htop
repo, based on `61c598b1`. Existing source changes are registration lines only
in `Makefile.am` and `linux/Platform.c`. No new runtime dependency is required.

- Discover i915 `8086:7d67` and its DRM device numbers dynamically, select the
  lowest supported PCI address, and invalidate histories on card removal/rebind.
  Filter fdinfo by device node, driver, and PCI identity before counting it.
- Deduplicate 64-bit client IDs across descriptors/processes; retain independent
  render/compute/video histories and counter high-water marks. New/missing/
  inaccessible data rebaseline instead of becoming lifetime spikes or false zero.
  Cache all readings once per newer htop tick and expire vanished client records.
- Preserve raw rates and video capacity; utilization is capped render+compute,
  while the shared E/D index caps raw video engine-equivalents at 100%, without
  dividing by two. Capacity controls plausibility checks, not this display's scale.
  Actual i915 timing exceeded wall time by about 9% in one valid busy interval;
  allow a bounded 25% accounting mismatch while rejecting gross counter jumps.
- Read requested GT0 clock and mutable maximum afresh; preserve zero and show
  unavailable for bad/missing readings. Check runtime status first; suspended
  samples skip dynamic clock/proc reads and clear histories before wake.
- Sum checked allocated `drm-total-system0` bytes once per readable client;
  never add resident/shared categories. Memory text/LED use approximate absolute
  units. No bar/percentage is offered without a meaningful global denominator.
  Heading text communicates visible-app scope and known partial/no-access states.
- Utilization, video, and clock support bar/text/graph/LED; the heading is text.
  The preview retains all eight AMD rows, then adds spacer/heading/four stats,
  giving fourteen rows in the third column.

Validation passed: normal build without warnings; IWYU/astyle; ten stateful
fake scenarios and three deliberate fault controls; Intel VA-API encode/decode
(peak E/D 32.7%/18.7%); Intel Vulkan graphics (usage 100%, requested 2000 MHz);
existing AMD/CPU/config/style-tool suites; whole-program ASan/UBSan meter
transitions across available modes. The final capacity-metadata correction was
retested with fake scenarios/negative controls and the sanitized display.
Full details and the two problems fixed during development are in AUDIT.md.

Remaining acceptance limits: no side-by-side Mission Center UI comparison;
external activity prevented an isolated real idle/autosuspend measurement.
Fake suspend/wake and source inspection passed, but do not prove real idle PM
conservation. A short uncontrolled CPU-cost comparison suggests about 1.7 extra
percentage points of one CPU core with the Intel block; repeat under controlled
conditions before treating that as a performance benchmark.
Dedicated copy/enhancement or isolated compute workloads were not tested.

The user started a game during final implementation review, so no further GPU
load tests were run after that point. At that handoff there were no driver,
settings, permission, or installation changes. The release followed separately.

## Release record: 2026-10-29

The user authorized installation and editing htop-gpu's config to put Intel under
AMD. Built and installed 3.5.3-9 with ten patches and zero compiler warnings.
The first nine patches are unchanged; patch 0010 captures the six-file source
working-tree diff (new sampler/meters and registration). A separate temporary
Git index included the new files without staging or committing the real repo.
All ten patches exactly reproduce all 368 source files from upstream 3.5.3.
Commit the Intel implementation before using `tools/export-patches.sh` again;
its commit-based export would otherwise omit the uncommitted Intel patch.

The package binary passed all 33 config-path checks and a copied-layout capture.
Fake Intel tests with negative controls and style passed again. Package diagnostics
match the stock baseline, and no package file overlaps stock htop. Installation
completed through desktop authentication; the installed binary matches the package
and both htop packages report zero altered files.

With no htop process running, backed up the config to
`~/.config/htop-gpu/htop-gpurc.bak-2026-10-29_14-47-46` and atomically changed only
third-column meter names/modes. Existing AMD rows and other settings are preserved.
An installed-binary capture using a disposable copy verified heading/utilization/
clock/memory/video below AMD. Stock htop/config and existing production source
were preserved. No new GPU load or permission/driver setting changes.
AUDIT.md records the release checks; remaining idle-PM/reference comparisons and
the source/tool/doc/packaging commits remain open. In progress nobody.

## Readout refinement: 2026-10-29

At the user's request, removed `requested` from the clock readout and `~` /
`allocated` from memory. Examples: `iGPU clock: 800MHz`, `iGPU mem: 4.00M`.
Only two display format strings changed; clock/memory sources, values, units,
validity, modes, descriptions, and the user's saved layout are unchanged.
Installed as 3.5.3-10 after style, fake Intel tests/negative controls, complete
sanitized-program display, package/source reproduction, and package/installed
display checks. The cached full sanitized build was updated with the changed
meter; no new live GPU workload or full unrelated regression suite was run.
Audit/release details are in AUDIT.md. Patch 0010/checksums updated without a
commit or push; prior uncommitted implementation remains. In progress nobody.

## Heading refinement: 2026-10-29

At the user's request, the normal heading is just `Intel iGPU`, without a colon,
`visible apps`, or partial-coverage suffix. Sleeping still shows `Intel iGPU: sleep`;
no-access/unavailable indications remain. Coverage details stay in the meter
descriptions. The sampler, metric values, and real config/layout are unchanged.
Five transitions in one full sanitized htop process (active, sleep, wake, access
denied, recovered) verified correct text and clearing of old suffixes.
Installed as 3.5.3-11 after normal/sanitized build, style, fake Intel tests/negative
controls, patch/source reproduction, and package/installed display checks.
AUDIT.md records validation/limits. Source/docs/patch 0010/PKGBUILD remain
uncommitted; no commit/push. In progress nobody.

## Finding 8 fix: 2026-10-29

Installed 3.5.3-12 after fixing access loss in `IntelGPU.c`. Keep separate
PID/starttime/FD-to-client references across process-directory/node-stat denial
and whole-proc access gaps. A missing previously identified client makes rates
and empty memory unavailable, rather than publishing false zero. A globally
readable shared alias still supplies the client once. Confirmed FD close, process
exit, and PID-generation changes expire obsolete ownership; unrelated protected
processes/FDs do not invalidate known readings. Device changes clear both maps.

Extended tests create stable process-starttime fixtures with spaced/parenthesized
comm names. All 18 stateful groups and three negative controls passed under
ASan/UBSan; old source fails ten new assertions. Six actual meter transitions
in one full sanitized htop process passed, including repeated directory denial,
FD-stat denial, and recovery. Passive real-host sampling and package/installed
checks passed without adding GPU workloads. Existing compact labels/layout and
both real configs are unchanged. AUDIT.md records details and remaining limits.
Source/test/docs/patch 0010/PKGBUILD remain uncommitted; no push. In progress nobody.
