#!/bin/bash
# Build the whole dev htop with AddressSanitizer + UndefinedBehaviorSanitizer into a separate
# binary, optionally reading a fake sysfs tree (from fake-sysfs.py), then rebuild the normal
# src/htop/htop. Both builds start from `make clean`, so this takes a minute.
# Run the result with sanitizer logs going to files, e.g.
#   ASAN_OPTIONS=log_path=/tmp/x/asan:detect_leaks=0 UBSAN_OPTIONS=log_path=/tmp/x/ubsan:print_stacktrace=1
# and no log files afterwards means no findings.
# Usage: build-htop-asan.sh <output binary> [fake AMD GPU sysfs root] [extra CPPFLAGS]
set -euo pipefail

here=$(dirname "$(readlink -f "$0")")
src=$(readlink -f "$here/../src/htop")
out=$1
cppflags=${3:-}
if [[ -n ${2:-} ]]; then
   root=$(readlink -f "$2")
   if [[ $root == *[[:space:]\"\\]* ]]; then
      echo "fake sysfs root must not contain spaces, quotes or backslashes: $root" >&2
      exit 1
   fi
   cppflags+=" -DAMDGPU_SYSFS_ROOT=\\\"$root\\\""
fi
sanitize="-fsanitize=address,undefined -fno-omit-frame-pointer"

rebuild_normal() {
   make -C "$src" -s clean
   make -C "$src" -s -j"$(nproc)" htop
}
trap rebuild_normal EXIT

make -C "$src" -s clean
make -C "$src" -s -j"$(nproc)" CFLAGS="-g -O1 $sanitize" LDFLAGS="$sanitize" CPPFLAGS="$cppflags" htop
cp "$src/htop" "$out"
echo "built $out (ASan + UBSan)"
