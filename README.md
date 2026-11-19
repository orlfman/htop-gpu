# htop-gpu

This is my own build of [htop](https://htop.dev) with GPU stats added to the header. Regular htop can show a combined GPU percentage, but it can't tell me anything about VRAM, temperatures, power or clocks, and it lumps my two GPUs together. So I added the meters I actually wanted.

It's built for my machine: an AMD Radeon RX 9070 XT, the Intel iGPU in my Core Ultra 7 270K Plus, and that CPU's power readings. It installs as `htop-gpu`, right next to the normal `htop`, so the regular one stays untouched and keeps getting updates.

Here's what the extra column looks like on my desktop:

```
Radeon RX 9070 XT
GPU[|||||                    7%]
VRM[||||||||       1.93G/15.9G]
Pwr[|||||||           33W/304W]
VCN[||||||                 10%]
Fan[                   stopped]
GPU temp: edge:44°C junction:46°C mem:46°C
GPU clock: 1529MHz
VRAM clock: 456MHz 7.3Gbps busy:2%

Intel iGPU
iGP[                        0%]
iGPU clock: 0MHz
iGPU mem: 180M
Vid[                    0% E/D]
```

And here it is next to MangoHud while playing Dune: Awakening, which is how I checked that the numbers line up: [htop-gpu](docs/game-load-test/htop-gpu-dune-awakening.png) and [MangoHud](docs/game-load-test/mangohud-dune-awakening.webp).

## What it shows

For the RX 9070 XT:

- GPU usage
- VRAM used out of the total
- Power draw against the power limit
- Video engine load (encoding and decoding share one engine on this card, so it's one number), with its clocks
- Fan speed, which just says "stopped" when the card is idle and the fan is off
- Edge, junction and memory temperatures, which turn yellow and then red as they get close to their limits
- GPU clock
- VRAM clock and speed, plus how busy the memory controller is

For the Intel iGPU:

- Usage, clock, memory and video encode/decode

Usage, video and allocated memory cover programs whose GPU counters htop can read. The requested clock comes from the GPU driver. A missing counter shows N/A.

For the CPU:

- Package power against the long term power limit (PL1), from Intel RAPL

There are also two headings you can put above a group of meters: one with the card's name, and one with the CPU's name ("Intel Core Ultra 7 270K Plus" here), like the "Intel iGPU" one.

All of them work like normal htop meters. You add them in F2 Setup and can show each one as a bar, text, graph or LED. Two exceptions: the headings are just text, and the Intel iGPU memory meter is text or LED only, since there's no total to draw a bar against.

## Will it work on my computer?

Partly. The AMD meters should work on any dedicated RX 6000, RX 7000 or RX 9000 card (RDNA 2, 3 and 4, and their Radeon Pro versions), and the heading shows that card's name. I only own an RX 9070 XT though, so the other cards are tested against made up copies of what the kernel driver reports, not on real hardware. If you try it on one, I'd like to hear how it goes. Integrated Radeon graphics and older cards show N/A.

The Intel meters recognize Tiger Lake and Rocket Lake integrated graphics (11th-gen Core), Alder Lake (12th-gen Core), Raptor Lake and its refresh, plus the Meteor, Arrow, Lunar, Panther, Wildcat and Nova Lake families listed in the Linux 7.3 PCI IDs. They support both `i915` and `xe`. The sampler picks the supported iGPU with the lowest PCI address and reads the metrics its driver exposes. Intel Arc desktop and laptop discrete GPUs are excluded. Live testing used a Core Ultra 7 270K Plus on `i915`; the other families and `xe` have simulated test coverage.

The CPU power meter needs to read the RAPL energy counter, which Linux keeps root only by default. I made mine readable with this udev rule in `/etc/udev/rules.d/99-rapl-read.rules`:

```
SUBSYSTEM=="powercap", KERNEL=="intel-rapl:0", ACTION=="add", RUN+="/usr/bin/chmod 0444 /sys%p/energy_uj"
```

It's locked down for a reason (the counter has been used for side channel attacks before), so decide for yourself whether that's okay on your machine. Without it the meter just says "no access".

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

The actual code lives in [orlfman/htop](https://github.com/orlfman/htop) on the `amdgpu-meters` branch, as a handful of commits on top of htop 3.5.3. I try to keep it close to upstream htop and follow their style, so moving to a new htop release is mostly a rebase.

This repo has everything around it:

- `packaging/` has the PKGBUILD and the patches exported from that branch
- `tools/` has the test scripts. There's quite a few, because I wanted to see these meters behave when files go missing, the card goes to sleep or permissions change, not just on a good day
- `PLAN.md` has the design notes and what I measured on the hardware
- `CHANGELOG.md` and `AUDIT.md` are the history and the review notes

I wrote this with a lot of help from AI coding agents (Claude and Codex), and kept them honest with tests and by checking the numbers against other tools.

## License

GPL 2.0 or later, same as htop. All the credit for htop itself goes to the htop developers.
