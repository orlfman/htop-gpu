#!/bin/bash
# Check the files htop-gpu adds to htop against upstream's own tooling:
#  - include-what-you-use with upstream's iwyu/htop.imp mapping (as iwyu/run_iwyu.sh does)
#  - the astyle baseline from docs/styleguide.md, shown as a diff (files are not touched)
# Only files added on top of the upstream tag are checked; upstream files are left as they are.
# Needs src/htop configured (./configure) for config.h.
# Usage: check-style.sh [extra files relative to src/htop or absolute]
set -uo pipefail

here=$(dirname "$(readlink -f "$0")")
src=$(readlink -f "$here/../src/htop")
cd "$src" || exit 1

base=$(git describe --tags --abbrev=0 HEAD)
mapfile -t files < <( { git diff --name-only --diff-filter=A "$base" -- '*.c' '*.h';
                        git ls-files --others --exclude-standard -- '*.c' '*.h'; } | sort -u)
files+=("$here/amdgpu-sample.c" "$@")

echo "upstream base: $base"
echo "checking: ${files[*]#"$here/"}"
status=0

echo
echo "== include-what-you-use"
# -w: config.h comes from the gcc configure, so clang would warn about gcc-only attributes;
# upstream's run_iwyu.sh reconfigures with clang instead, which would wipe the dev build
iwyu_flags=(-Xiwyu --no_comments -Xiwyu --no_fwd_decl -Xiwyu "--mapping_file=$src/iwyu/htop.imp" -w
            -std=c99 -pedantic -D_DEFAULT_SOURCE -D_XOPEN_SOURCE=600 -DHAVE_CONFIG_H
            -I"$src" -I"$src/linux" $(pkg-config --cflags libnl-3.0) -DSYSCONFDIR='"/etc"')
for f in "${files[@]}"; do
   [[ $f == *.c ]] || continue
   out=$(include-what-you-use "${iwyu_flags[@]}" -c "$f" -o /dev/null 2>&1)
   # IWYU also reports on the .c file's own header; anything not "correct" is a finding
   if grep -q -E 'should (add|remove) these lines|The full include-list|error:' <<<"$out"; then
      echo "$out"
      status=1
   else
      grep -E 'has correct #includes' <<<"$out"
   fi
done

echo
echo "== astyle (docs/styleguide.md baseline)"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
for f in "${files[@]}"; do
   cp "$f" "$tmp/check"
   astyle -n -q -xb -s3 -p -xg -c -k1 -W1 -H "$tmp/check"
   if ! diff -u --label "$f" --label "$f (astyle)" "$f" "$tmp/check"; then
      status=1
   else
      echo "${f#"$here/"}: unchanged"
   fi
done

echo
[[ $status == 0 ]] && echo "STYLE OK" || echo "STYLE FINDINGS ABOVE"
exit $status
