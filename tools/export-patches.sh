#!/bin/bash
# Export the amdgpu-meters commits of src/htop as patches into packaging/, then update the
# PKGBUILD's _patches list and checksums. Run after committing in src/htop.
# Usage: export-patches.sh
set -euo pipefail

here=$(dirname "$(readlink -f "$0")")
src=$(readlink -f "$here/../src/htop")
pkg=$(readlink -f "$here/../packaging")

base=$(git -C "$src" describe --tags --abbrev=0 amdgpu-meters)
pkgver=$(sed -n 's/^pkgver=//p' "$pkg/PKGBUILD")
if [[ $base != "$pkgver" ]]; then
   echo "branch is based on $base but PKGBUILD has pkgver=$pkgver; update pkgver first" >&2
   exit 1
fi

rm -f "$pkg"/*.patch
git -C "$src" format-patch --quiet --no-signature -o "$pkg" "$base..amdgpu-meters"
mapfile -t patches < <(cd "$pkg" && ls -- *.patch)

python3 -I - "$pkg/PKGBUILD" "${patches[@]}" <<'EOF'
import re, sys

path, patches = sys.argv[1], sys.argv[2:]
text = open(path).read()
block = "_patches=(\n" + "".join(f"  {p}\n" for p in patches) + ")"
text, n = re.subn(r"_patches=\(\n(?:  .*\n)*\)", block, text)
if n != 1:
    sys.exit("PKGBUILD: no _patches=( ... ) block found")
open(path, "w").write(text)
EOF

(cd "$pkg" && updpkgsums)
echo "exported ${#patches[@]} patches from $base..amdgpu-meters"
