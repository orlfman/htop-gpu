# htop-gpu

This is my own build of [htop](https://htop.dev) with GPU stats and CPU power added to the header. Regular htop can show a combined GPU percentage, but it can't tell me anything about VRAM, temperatures, power or clocks, it lumps my two GPUs together, and it has no idea how many watts the CPU is pulling. So I added the meters I actually wanted.

It started out built for my own machine (an AMD Radeon RX 9070 XT and the Intel iGPU in my Core Ultra 7 270K Plus), but it now works with recent AMD cards, Intel iGPUs, and the power readings of both Intel and AMD CPUs. It installs as `htop-gpu`, right next to the normal `htop`, so the regular one stays untouched and keeps getting updates.

Here's what it looks like on my desktop. The two CPU columns on the left show the CPU's name on top and its power at the bottom, and the right column has the RX 9070 XT and the Intel iGPU, which was busy playing a video in mpv:

![htop-gpu with the CPU, Radeon RX 9070 XT and Intel iGPU meters](docs/htop-gpu-desktop.png)

And here it is next to MangoHud while playing Dune: Awakening, which is how I checked that the numbers line up: [htop-gpu](docs/game-load-test/htop-gpu-dune-awakening.png) and [MangoHud](docs/game-load-test/mangohud-dune-awakening.webp).

## What it shows

For AMD cards:

- GPU usage
- VRAM used out of the total
- Power draw against the power limit
- Video engine load (encoding and decoding share one engine, so it's one number), with its clocks
- Fan speed, which just says "stopped" when the card is idle and the fan is off
- Edge, junction and memory temperatures, which turn yellow and then red as they get close to their limits
- GPU clock
- VRAM clock and speed, plus how busy the memory controller is

For the Intel iGPU:

- Usage, clock, memory and video encode/decode

Usage, video and memory add up the programs htop can read, which in practice means your own. When it can't get a reading, the meter says N/A instead of guessing. The clock comes straight from the driver.

For Intel and AMD CPUs:

- Package power in watts, against the CPU's long term power limit when it reports one

The CPU and Radeon headings show their model names. The Intel heading shows the model from the system PCI database too. On my machine it shows `Arrow Lake-S [Intel Graphics]`. If the database has no name for the device, it shows `Intel iGPU`.

All of them work like normal htop meters. You add them in F2 Setup and can show each one as a bar, text, graph or LED. Two exceptions: the headings are just text, and the Intel iGPU memory meter is text or LED only, since there's no total to draw a bar against. Like htop's own CPU and memory meters, they keep updating when you pause the process list with `Z`.

## Will it work on my computer?

Partly. The AMD meters should work on any dedicated RX 6000, RX 7000 or RX 9000 card (RDNA 2, 3 and 4, and their Radeon Pro versions), and the heading shows that card's name. I only own an RX 9070 XT though, so the other cards are tested against made up copies of what the kernel driver reports, not on real hardware. If you try it on one, I'd like to hear how it goes. Integrated Radeon graphics and older cards show N/A.

The Intel meters work with the integrated graphics in 11th gen Core and newer: Tiger Lake and Rocket Lake, Alder Lake, Raptor Lake and its refresh, Meteor Lake, Arrow Lake, Lunar Lake, Panther Lake, Wildcat Lake and Nova Lake. Both the `i915` kernel driver and the newer `xe` one are supported. Intel Arc and other discrete Intel GPUs aren't covered. I've tested my 270K Plus on both drivers, and the other chips only against made up copies of what the driver reports, same as the AMD cards.

On `xe`, just reading the iGPU's counters keeps it awake. So if you set htop to refresh faster than about once a second, the iGPU meters only update every 1.3 seconds or so, which leaves the iGPU time to go to sleep when nothing is using it. At htop's default speed you won't notice. If you've set the iGPU to always stay on, they update every refresh.

htop's own `GPU%` and `GPU_TIME` process columns can't use `xe`'s numbers (`xe` counts in a different unit), and reading them would keep the iGPU awake too. So those columns skip `xe` and still count any other GPU a program uses. The iGPU meters in the header read `xe` properly.

To find out which programs are using the iGPU, htop-gpu looks at the files they have open. It's careful not to ask network shares or FUSE mounts about those files, so a hung NFS or SMB share shouldn't freeze it.

The CPU power meter reads the CPU's own energy counter, which Linux shows under `intel-rapl` for both Intel and AMD CPUs (the name is historical). Some Intel CPUs also have a second copy of it under `intel-rapl-mmio`; htop-gpu uses whichever one it can read and counts each CPU once. Intel CPUs usually report a long term power limit too, and then the bar and graph fill up against it. AMD CPUs don't report one through this interface, so there the meter just shows the watts. I've only tested this on my 270K Plus; AMD CPUs are tested against made up copies of their counters, so if you try it on one, I'd like to hear how it goes.

Linux keeps the energy counter root only by default. I made mine readable with this udev rule in `/etc/udev/rules.d/99-rapl-read.rules`:

```
SUBSYSTEM=="powercap", KERNEL=="intel-rapl:0", ACTION=="add", RUN+="/usr/bin/chmod 0444 /sys%p/energy_uj"
```

If your counter is under `intel-rapl-mmio:0`, or you have more than one CPU package, list those too, for example `KERNEL=="intel-rapl:[0-9]|intel-rapl-mmio:[0-9]"`. I haven't needed that version myself, so double check it works on yours.

It's locked down for a reason (the counter has been used for side channel attacks before), so decide for yourself whether that's okay on your machine. Without access the meter just says `no access`.

## Installing

It's packaged for Arch and CachyOS. The PKGBUILD downloads the official htop 3.5.3 release and applies my changes as patches:

```
git clone https://github.com/orlfman/htop-gpu.git
cd htop-gpu/packaging
makepkg -si
```

Then run `htop-gpu`. The first time it starts it copies your normal htop settings into `~/.config/htop-gpu/htop-gpurc`, and from then on the two keep separate configs. Your regular htop config is only ever read, never changed.

Since pacman doesn't know about this package, it won't update it. `tools/check-upstream.sh` tells you when a newer htop is out.

To get rid of it, `sudo pacman -R htop-gpu`. Regular htop doesn't care either way.

## Where things are

The actual code is the patches in [`packaging/`](packaging/), a stack of commits on top of htop 3.5.3. I keep the commits themselves in a separate htop clone and export them from there. I try to keep it close to upstream htop and follow their style, so moving to a new htop release is mostly a rebase.

This repo has everything:

- `packaging/` has the PKGBUILD and the patches, one per commit
- `tools/` has the test scripts. There's quite a few, because I wanted to see these meters behave when files go missing, the card goes to sleep or permissions change, not just on a good day
- `PLAN.md` has the design notes and what I measured on the hardware
- `CHANGELOG.md` and `AUDIT.md` are the history and the review notes

I wrote this with a lot of help from AI coding agents (Claude and Codex), and kept them honest with tests and by checking the numbers against other tools.

## License

GPL 2.0 or later, same as htop (see [LICENSE](LICENSE)). All the credit for htop itself goes to the htop developers.
