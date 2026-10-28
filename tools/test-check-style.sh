#!/bin/bash
# Check that tools/check-style.sh can fail: real findings exit 1, a missing or failing
# include-what-you-use / astyle exits 2, and only a real clean run prints STYLE OK (AUDIT.md
# finding 3). Uses fake tools and throwaway files; nothing in the repo is changed.
# Usage: test-check-style.sh
set -uo pipefail

here=$(dirname "$(readlink -f "$0")")
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
fails=0

# run check-style.sh with the given PATH and extra files; sets rc and out
style() {
   local path=$1
   shift
   out=$(PATH=$path "$here/check-style.sh" "$@" 2>&1)
   rc=$?
}

check() {
   local name=$1 want=$2
   if [[ $rc == "$want" ]] && { [[ $want == 0 ]] || ! grep -q 'STYLE OK' <<<"$out"; }; then
      echo "  ok   $name (exit $rc)"
   else
      echo "  FAIL $name: exit $rc, wanted $want; last line: $(tail -1 <<<"$out")"
      fails=$((fails + 1))
   fi
}

# fake tools that fail the way a broken install would
mkdir -p "$tmp/fail-iwyu" "$tmp/fail-astyle" "$tmp/fail-both"
fake() {
   printf '#!/bin/sh\necho "%s: unavailable" >&2\nexit 127\n' "$2" > "$1/$2"
   chmod +x "$1/$2"
}
fake "$tmp/fail-iwyu" include-what-you-use
fake "$tmp/fail-astyle" astyle
fake "$tmp/fail-both" include-what-you-use
fake "$tmp/fail-both" astyle

# a PATH with everything from /usr/bin except the two tools
mkdir -p "$tmp/no-tools"
for f in /usr/bin/*; do
   case ${f##*/} in
      include-what-you-use|astyle) ;;
      *) ln -s "$f" "$tmp/no-tools/${f##*/}" ;;
   esac
done

# extra files with a real finding each: an unused include, and tab indentation
printf '#include <stdio.h>\n#include <string.h>\n\nint main(void) {\n   puts("x");\n   return 0;\n}\n' > "$tmp/iwyu-finding.c"
printf '#include <stdio.h>\n\nint main(void) {\n\tputs("x");\n\treturn 0;\n}\n' > "$tmp/astyle-finding.c"

echo "[check-style.sh exit codes]"
style "$PATH"
check "real tools, clean files" 0
style "$tmp/fail-iwyu:$PATH"
check "include-what-you-use fails" 2
style "$tmp/fail-astyle:$PATH"
check "astyle fails" 2
style "$tmp/fail-both:$PATH"
check "both tools fail" 2
style "$tmp/no-tools"
check "both tools missing" 2
style "$PATH" "$tmp/iwyu-finding.c"
check "real IWYU finding" 1
style "$PATH" "$tmp/astyle-finding.c"
check "real astyle finding" 1

echo
[[ $fails == 0 ]] && echo "ALL PASSED" || echo "$fails FAILED"
exit $((fails > 0))
