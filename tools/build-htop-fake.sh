#!/bin/bash
# Build a copy of the dev htop whose AMDGPU sampler reads a fake sysfs tree (from fake-sysfs.py)
# instead of /sys, to check how the meters look for a sleeping, missing or broken card.
# Only linux/AMDGPU.o is rebuilt with the fake root; src/htop/htop is rebuilt normally afterwards.
# Usage: build-htop-fake.sh <fake sysfs root> <output binary>
set -euo pipefail

here=$(dirname "$(readlink -f "$0")")
src=$(readlink -f "$here/../src/htop")
root=$(readlink -f "$1")
out=$2

if [[ $root == *[[:space:]\"\\]* ]]; then
   echo "fake sysfs root must not contain spaces, quotes or backslashes: $root" >&2
   exit 1
fi

rebuild_normal() {
   touch "$src/linux/AMDGPU.c"
   make -C "$src" -s -j"$(nproc)" htop
}

# bring everything else up to date first, so the fake root only ever reaches linux/AMDGPU.o
make -C "$src" -s -j"$(nproc)" htop
trap rebuild_normal EXIT

touch "$src/linux/AMDGPU.c"
make -C "$src" -s -j"$(nproc)" CPPFLAGS="-DAMDGPU_SYSFS_ROOT=\\\"$root\\\"" htop
cp "$src/htop" "$out"
echo "built $out (sysfs root $root)"
