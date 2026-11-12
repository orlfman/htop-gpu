#!/bin/bash
# Build the AMDGPU sampler test driver against src/htop (./configure must have run there).
# Usage: build-sampler.sh <output binary> [sysfs root, default /sys] [amdgpu.ids file, default libdrm's]
set -euo pipefail

here=$(dirname "$(readlink -f "$0")")
src=$here/../src/htop
out=$1
root=${2:-/sys}
ids=${3:-/usr/share/libdrm/amdgpu.ids}

gcc -std=c99 -Wall -Wextra -Wshadow -Wformat-nonliteral -Werror -O1 -g \
    -fsanitize=address,undefined -fno-omit-frame-pointer \
    -I"$src" -I"$src/linux" -DAMDGPU_SYSFS_ROOT="\"$root\"" -DAMDGPU_IDS_FILE="\"$ids\"" \
    "$here/amdgpu-sample.c" "$src/linux/AMDGPU.c" "$src/linux/Compat.c" "$src/XUtils.c" \
    -lm -o "$out"
