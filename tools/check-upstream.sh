#!/bin/bash
# Show whether a newer htop is out than the one htop-gpu is built on. htop-gpu replaces the
# repo htop, so pacman -Syu never updates it; run this now and then instead.
# Usage: check-upstream.sh
set -uo pipefail

here=$(dirname "$(readlink -f "$0")")
src=$(readlink -f "$here/../src/htop")
pkg=$(readlink -f "$here/../packaging")

built=$(sed -n 's/^pkgver=//p' "$pkg/PKGBUILD")
installed=$(pacman -Q htop-gpu 2>/dev/null | awk '{print $2}')
repo=$(pacman -Si htop 2>/dev/null | awk -F': ' '/^Version/ {print $2; exit}')
latest=$(git -C "$src" ls-remote --tags --refs upstream 2>/dev/null |
         sed 's|.*refs/tags/||' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1)

echo "htop-gpu PKGBUILD:    $built"
echo "htop-gpu installed:   ${installed:-not installed}"
echo "repo htop:            ${repo:-unknown}"
echo "upstream latest tag:  ${latest:-unknown (no network?)}"

if [[ -z $latest ]]; then
   exit 1
elif [[ $(printf '%s\n' "$built" "$latest" | sort -V | tail -1) != "$built" ]]; then
   echo "-> htop $latest is out: rebase amdgpu-meters onto it (PLAN.md, \"Staying close to upstream\")"
else
   echo "-> up to date"
fi
