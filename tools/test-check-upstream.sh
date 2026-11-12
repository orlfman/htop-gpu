#!/bin/bash
# Tests for check-upstream.sh in throwaway copies of this repository's layout, with local git
# repositories standing in for htop's (no network): a fresh checkout without the developer
# clone src/htop (AUDIT.md finding 18), one with it, and unreachable repositories.
# Usage: test-check-upstream.sh
set -uo pipefail

here=$(dirname "$(readlink -f "$0")")
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
failures=0

check() {   # check <name> <command...>
   local name=$1
   shift
   if "$@"; then
      echo "  ok   $name"
   else
      echo "  FAIL $name"
      failures=$((failures + 1))
   fi
}

# a repository with the given tags, standing in for htop's
upstream() {   # upstream <dir> <tag...>
   local dir=$1
   shift
   git init -q "$dir"
   git -C "$dir" -c user.name=t -c user.email=t@example.invalid commit -q --allow-empty -m release
   local tag
   for tag in "$@"; do
      git -C "$dir" tag "$tag"
   done
}

# a copy of what a fresh clone of this repository has: no src/
project() {   # project <dir> <pkgver>
   mkdir -p "$1/tools" "$1/packaging"
   cp "$here/check-upstream.sh" "$1/tools/"
   printf 'pkgname=htop-gpu\npkgver=%s\npkgrel=1\n' "$2" >"$1/packaging/PKGBUILD"
}

run() {   # run <project dir> [upstream url]; sets $out and $rc
   out=$(HTOP_UPSTREAM_URL=${2:-} "$1/tools/check-upstream.sh" 2>&1)
   rc=$?
}

upstream "$tmp/htop-same" 3.5.2 3.5.3 3.5.3-rc1 not-a-release
upstream "$tmp/htop-newer" 3.5.3 3.10.0 3.9.9

echo "[fresh checkout without src/htop]"
project "$tmp/fresh" 3.5.3
run "$tmp/fresh" "$tmp/htop-same"
check "same release: up to date, exit 0" test "$rc" -eq 0 -a -z "${out##*upstream latest tag:  3.5.3
-> up to date*}"
run "$tmp/fresh" "$tmp/htop-newer"
check "newer release: reported (3.10.0 sorts above 3.9.9), exit 0" test "$rc" -eq 0 -a -z "${out##*-> htop 3.10.0 is out*}"
run "$tmp/fresh" "$tmp/no-such-repository"
check "unreachable repository: exit 1 and says where it asked" \
   test "$rc" -eq 1 -a -z "${out##*could not read htop\'s release tags from $tmp/no-such-repository*}"

echo "[developer checkout: src/htop with an upstream remote]"
project "$tmp/dev" 3.5.3
git init -q "$tmp/dev/src/htop"
git -C "$tmp/dev/src/htop" remote add upstream "$tmp/htop-newer"
run "$tmp/dev" "$tmp/htop-same"
check "the clone's remote is asked, not the URL" test "$rc" -eq 0 -a -z "${out##*-> htop 3.10.0 is out*}"
git -C "$tmp/dev/src/htop" remote set-url upstream "$tmp/no-such-repository"
run "$tmp/dev" "$tmp/htop-same"
check "unreachable remote: exit 1 and names the remote" \
   test "$rc" -eq 1 -a -z "${out##*could not read htop\'s release tags from src/htop remote*}"

echo "[src/htop without an upstream remote]"
git -C "$tmp/dev/src/htop" remote remove upstream
run "$tmp/dev" "$tmp/htop-same"
check "falls back to the URL" test "$rc" -eq 0 -a -z "${out##*-> up to date*}"

echo
if [[ $failures -eq 0 ]]; then
   echo "ALL PASSED"
else
   echo "$failures FAILED"
   exit 1
fi
