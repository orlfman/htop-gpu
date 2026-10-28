#!/usr/bin/env python3
# Decode amdgpu gpu_metrics v1.3 (the layout the 9070 XT reports: 120 bytes, rev 1.3).
import struct, sys

FIELDS = [
    ("H", "structure_size"), ("B", "format_revision"), ("B", "content_revision"),
    ("H", "temperature_edge"), ("H", "temperature_hotspot"), ("H", "temperature_mem"),
    ("H", "temperature_vrgfx"), ("H", "temperature_vrsoc"), ("H", "temperature_vrmem"),
    ("H", "average_gfx_activity"), ("H", "average_umc_activity"), ("H", "average_mm_activity"),
    ("H", "average_socket_power"), ("Q", "energy_accumulator"), ("Q", "system_clock_counter"),
    ("H", "average_gfxclk_frequency"), ("H", "average_socclk_frequency"), ("H", "average_uclk_frequency"),
    ("H", "average_vclk0_frequency"), ("H", "average_dclk0_frequency"),
    ("H", "average_vclk1_frequency"), ("H", "average_dclk1_frequency"),
    ("H", "current_gfxclk"), ("H", "current_socclk"), ("H", "current_uclk"),
    ("H", "current_vclk0"), ("H", "current_dclk0"), ("H", "current_vclk1"), ("H", "current_dclk1"),
    ("I", "throttle_status"), ("H", "current_fan_speed"),
    ("H", "pcie_link_width"), ("H", "pcie_link_speed"), ("H", "padding"),
    ("I", "gfx_activity_acc"), ("I", "mem_activity_acc"),
    ("4H", "temperature_hbm"), ("Q", "firmware_timestamp"),
    ("H", "voltage_soc"), ("H", "voltage_gfx"), ("H", "voltage_mem"), ("H", "padding1"),
    ("Q", "indep_throttle_status"),
]
FMT = "<" + "".join(f for f, _ in FIELDS)


def read(path="/sys/bus/pci/devices/0000:04:00.0/gpu_metrics"):
    raw = open(path, "rb").read()
    assert struct.calcsize(FMT) == 120, struct.calcsize(FMT)
    vals = struct.unpack(FMT, raw[:120])
    out, i = {}, 0
    for f, name in FIELDS:
        n = 4 if f == "4H" else 1
        out[name] = vals[i] if n == 1 else vals[i:i + n]
        i += n
    return out


if __name__ == "__main__":
    for k, v in read(*sys.argv[1:]).items():
        unset = v in (0xFFFF, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF)
        print(f"{k:26} {v}{'  (unset)' if unset else ''}")
