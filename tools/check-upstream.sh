#!/bin/bash
# Show whether a newer htop is out than the one htop-gpu is built on. htop-gpu is its own
# package next to the repo htop, so pacman -Syu never updates it; run this now and then instead.
# Needs only this repository: the tags come from the developer clone's "upstream" remote when
# src/htop exists (see AGENTS.md), otherwise straight from htop's repository.
# Usage: check-upstream.sh        (HTOP_UPSTREAM_URL overrides the repository asked without src/htop)
set -uo pipefail

here=$(dirname "$(readlink -f "$0")")
src=$here/../src/htop
pkg=$(readlink -f "$here/../packaging")
url=${HTOP_UPSTREAM_URL:-https://github.com/htop-dev/htop.git}

built=$(sed -n 's/^pkgver=//p' "$pkg/PKGBUILD")
installed=$(pacman -Q htop-gpu 2>/dev/null | awk '{print $2}')
repo=$(pacman -Si htop 2>/dev/null | awk -F': ' '/^Version/ {print $2; exit}')

if git -C "$src" remote get-url upstream >/dev/null 2>&1; then
   from="src/htop remote \"upstream\""
   tags=$(git -C "$src" ls-remote --tags --refs upstream 2>/dev/null)
else
   from=$url
   tags=$(git ls-remote --tags --refs "$url" 2>/dev/null)
fi
latest=$(sed 's|.*refs/tags/||' <<<"$tags" | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1)

echo "htop-gpu PKGBUILD:    $built"
echo "htop-gpu installed:   ${installed:-not installed}"
echo "repo htop:            ${repo:-unknown}"
echo "upstream latest tag:  ${latest:-unknown}"

if [[ -z $latest ]]; then
   echo "-> could not read htop's release tags from $from (no network?)" >&2
   exit 1
elif [[ $(printf '%s\n' "$built" "$latest" | sort -V | tail -1) != "$built" ]]; then
   echo "-> htop $latest is out: rebase amdgpu-meters onto it (PLAN.md, \"Staying close to upstream\")"
else
   echo "-> up to date"
fi
