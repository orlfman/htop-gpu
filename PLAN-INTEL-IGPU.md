# Intel iGPU: secondary implementation plan

Date: 2026-10-28 (America/Phoenix). Author: Codex.
Status: investigation complete; implementation has not started.
This supplements PLAN.md and follows AGENTS.md.
The user wants Intel iGPU stats below the RX 9070 XT stats in the existing third column.

## Recommended approach

Add an independent Intel sampler and meters, starting with the currently bound i915 driver.
Use readable DRM client counters for activity and per-GT sysfs for clocks.
Describe activity as covering visible applications, rather than promising device-wide coverage.
Device-wide PMU access is currently denied to the normal user; treat it as an optional later backend.
Keep the existing AMD meters and CPU package-power meter intact.

The initial block should show render, compute, copy, video, video-enhance activity, and render/media clocks.
Do not add placeholder power, temperature, fan, or dedicated-VRAM bars for sources this machine does not expose.
Memory reporting needs a separate, carefully labeled design and can follow the activity/clocks work.

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
| Outer baseline | `8601dca3e9715af70a099d40b1a707ea63766e93` |
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
The header must communicate that scope, for example `Intel iGPU: visible apps`.

The [DRM usage-statistics specification](https://docs.kernel.org/gpu/drm-usage-stats.html) defines client identity, engine capacities, counter behavior, and memory categories.
The [i915 implementation](https://raw.githubusercontent.com/torvalds/linux/v7.3/drivers/gpu/drm/i915/i915_drm_client.c) confirms accounting per engine class.

### Clock sources

Use `/sys/class/drm/<Intel card>/gt/gt*/`, rather than the legacy card-wide frequency aliases.
The latter cannot express both domains clearly.

| Attribute | GT0 observed | GT1 observed | Meaning in the proposed UI |
| --- | --- | --- | --- |
| `rps_act_freq_mhz` | 0 MHz in sampled idle/media intervals | 0 or 500 MHz | Actual render / media clocks |
| `rps_cur_freq_mhz` | 0 MHz when sampled idle | 0 MHz when sampled idle | Requested clock; do not silently substitute for actual |
| `rps_min_freq_mhz` | 550 MHz | 100 MHz | Configured minimum request |
| `rps_max_freq_mhz` | 2000 MHz | 1400 MHz | Current configured maximum request |
| `rps_RP0_freq_mhz` | 2000 MHz | 1400 MHz | Hardware maximum exposed here |

GT1 reaching 500 MHz during the pinned video workload supports its media-domain identification on this host.
Render load and a positive GT0 clock still need a dedicated validation workload.
Retain per-device GT mapping explicitly; do not generalize these IDs to every Intel GPU.
Zero actual frequency is a reported value, even when the device runtime state is active.
Missing/unreadable values are unavailable, not zero.
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

### Metrics deliberately deferred

No hwmon directory was found under this Intel PCI device, so no usable iGPU temperature or direct power sensor was established.
RAPL exposes package-0, core, and uncore; only package energy is readable with the existing rule.
The uncore counter is unreadable and has not been validated as an isolated graphics-power measurement on this platform.
Do not reuse CPU package watts or temperature as iGPU watts or temperature.

The iGPU's client memory categories describe shared-system-memory allocations, not a discrete card's dedicated VRAM pool.
Summing client resident bytes can count shared buffers repeatedly even after duplicate descriptors are removed.
Defer a global memory bar until there is a defensible total and sharing policy.
A later text-only visible-client allocation figure must explain its scope and possible sharing overlap.
Do not invent a VRAM capacity, use all system RAM as a fake VRAM limit, or apply the RX 9070 XT's GDDR6 clock conversion.
There is no separate iGPU fan sensor in this inventory.

## Live proof completed

A six-second, 1080p60 H.264 VA-API encode was pinned to the Intel render path and wrote to the null muxer.
It exited 0 with no error output and created no video file.
Ten snapshots identified one Intel client, capacity two for video, and 82,544 KiB of resident system memory for that client.
Across approximately 4.507 seconds of sampled intervals, its video counter increased by 1,330,747,548 ns.
That is about 14.76% averaged across both video engines for the sampled interval, not 14.76% render utilization.
GT0 remained 0 MHz in those snapshots; GT1 was observed at 500 MHz during part of the workload.
This validates the video-counter path; it does not validate render, compute, copy, enhancement load, or video decode.

Device runtime state was seen both suspended and active during the investigation.
The cause of changes outside the explicit workload was not isolated.
A passive monitoring loop must be tested to ensure it does not keep the iGPU awake.

## Proposed position and meter names

Keep `header_layout=three_33_34_33` and append to `column_meters_2`, after the existing eight AMD meters.
The current left and middle columns each have sixteen meter rows.
The following proposal also uses sixteen rows in the right column at the default modes, subject to a real terminal check:

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
Intel iGPU: visible apps  new text heading
Rnd [render activity]
Cmp [compute activity]
Cpy [copy activity]
Vid [video activity]
Vfx [video enhancement]
iGPU clock: render:...MHz media:...MHz
```

| Internal name proposed | Caption | Default mode | Source |
| --- | --- | --- | --- |
| `IntelGPUInfo` | `Intel iGPU: ` | Text | Device identity, visibility/backend status |
| `IntelGPURender` | `Rnd` | Bar | render-class counter deltas |
| `IntelGPUCompute` | `Cmp` | Bar | compute-class counter deltas |
| `IntelGPUCopy` | `Cpy` | Bar | copy-class counter deltas |
| `IntelGPUVideo` | `Vid` | Bar | video-class deltas, capacity two here |
| `IntelGPUEnhance` | `Vfx` | Bar | video-enhance-class deltas |
| `IntelGPUClock` | `iGPU clock: ` | Text | Actual GT0 and GT1 clocks |

These are proposed names for implementation, not names supported by the installed binary yet.
Keep each activity class separate; summing render, compute, copy, and video would not give a meaningful single 0–100% GPU percentage.
For a graph/bar form of the combined clock meter, use render clock against its own maximum; media clock remains additional text, like secondary values in existing meters.
The text heading is informational; activity meters need all four normal display modes.
Placement changes happen only after implementation passes, with a backup and no htop-gpu process running while its real config is edited.
No layout/config change was made during this planning request.

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
   For a given class, sum valid client busy-time deltas and divide by elapsed nanoseconds and that class's hardware capacity, then multiply by 100.
   Do not sum capacity once per client; capacity two describes the device's video-engine group.
   Missing capacity defaults to one; reject zero, malformed, or conflicting capacity reports.
5. Baseline newly seen clients; do not count their lifetime history as activity in the current tick.
   Keep a counter high-water mark on temporary backward reports, as specified by the DRM ABI.
   Confirmed device reset/removal establishes a new generation and fresh histories.
   Client exit, PID/FD reuse, skipped/inaccessible reads, and changing client sets must not cause negative values or spikes.
6. Represent validity and visibility separately from percentages.
   A partial visible-client result must not be labeled device-wide.
   First samples and insufficient history are unavailable; valid idle deltas are zero.
   Do not silently clamp large accounting errors into a plausible 100% reading.
7. Read actual clocks separately from requested clocks and refresh mutable scaling values.
   One successful read must not prevent future read failures and recovery from being observed.
8. Cache the entire result for same/older `host->monotonicMs` calls.
   Release transient resources and bound history storage; expire stale clients without losing correctness across brief access gaps.

An optional later PMU backend should report its device-wide scope explicitly, rebaseline on backend switches, and preserve the unprivileged fallback.
Derive PMU event type, CPU mask, and event configs dynamically rather than copying this boot's numbers.

## Implementation stages and acceptance

1. **Standalone probe and fixtures.**
   Add a small `tools/intel-gpu-sample.c` driver, fake sysfs/proc roots, and `tools/test-intel-gpu.py`.
   First prove scanner semantics, clock validity, and failure/recovery without touching htop's UI.
   Use measured ABI examples; store sanitized fixture data rather than live PIDs or unrelated process contents.
2. **Read-only sampler.**
   Implement i915 discovery, per-tick caching, sleep handling, per-client deltas, capacity normalization, and clocks.
   Benchmark scan cost and idle CPU overhead against stock htop and the existing build before optimizing.
   Do not require a new runtime command, daemon, package, or privileged htop process.
3. **Meters and disposable layout.**
   Add the heading and separate meters; reuse existing htop colors and display machinery.
   Verify the proposed sixteen-row block in the third column with both AMD and Intel enabled.
4. **Live validation.**
   Repeat the pinned Intel encode, add Intel decode and render/compute workloads, and check the appropriate class increases while unrelated classes remain sensible.
   Validate both actual clocks, transitions back to idle, and suspend/wake without monitoring-induced wakeups.
   Compare like-for-like with nvtop or a separately authorized intel_gpu_top reference; these tools are not production dependencies.
5. **Release and placement.**
   Run required existing suites, new Intel tests, style, full sanitized meter checks, packaging diagnostics, and config-path checks.
   Commit/export patches, bump pkgrel, build and verify the package, then install and append the block to the user's backed-up layout when that implementation/release work is requested.
   Record all validation in AUDIT.md and finish the shared handoff in PLAN.md/CHANGELOG.md.

Required stateful regression cases include mixed Intel/AMD clients; duplicate descriptors and shared/forked clients; reused IDs and process exit; independent classes; video capacities one/two/malformed; first sample; same/older ticks; partial access; disappearing files; temporary backward counters; device reset; node/GT renumbering; zero clocks; late/mutable limits; and sleep/wake.
Use the same running sampler across transitions, and include negative controls that deliberately break device filtering, deduplication, and capacity normalization.
Run new sampler tests under ASan/UBSan and verify actual meter displays and totals, not only JSON results.

## Open decisions and limits

The initial recommendation is the unprivileged visible-app backend, with no permission changes.
Device-wide PMU access, reliable global memory totals, isolated iGPU power, and temperature require separate investigation or approval where system access changes are involved.
Initial GT mapping is host-specific; xe and other Intel PCI IDs are future work.
Additional CPU-package discovery from AUDIT.md finding 7 remains deferred and is unrelated to this plan.

This investigation did not modify production source, binaries, packages, permissions, drivers, or user configs.
The only workload was the brief pinned Intel encode; no htop implementation or installation was performed.
