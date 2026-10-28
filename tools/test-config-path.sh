#!/bin/bash
# Check where htop-gpu reads and writes its configuration, in throwaway home folders:
# its own ~/.config/htop-gpu/htop-gpurc, seeded from stock htop's files, which stay untouched.
# Usage: test-config-path.sh [htop binary, default src/htop/htop]
set -uo pipefail

here=$(dirname "$(readlink -f "$0")")
htop=$(readlink -f "${1:-$here/../src/htop/htop}")
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
fails=0

check() {
   if eval "$2"; then
      echo "  ok   $1"
   else
      echo "  FAIL $1"
      fails=$((fails + 1))
   fi
}

# A stock htoprc and an htop-gpurc that differ, so the header shows which one was read
stock_rc() {
   printf '%s\n' 'htop_version=3.5.3' 'config_reader_min_version=3' 'header_layout=one_100' \
      'column_meters_0=Hostname' 'column_meter_modes_0=2' > "$1"
}
own_rc() {
   printf '%s\n' 'htop_version=3.5.3' 'config_reader_min_version=3' 'header_layout=one_100' \
      'column_meters_0=Uptime' 'column_meter_modes_0=2' > "$1"
}
run() {
   env -u HTOPRC -u XDG_CONFIG_HOME "$@" python3 -I "$here/htop-capture.py" - "$htop" 2 > "$tmp/screen"
}
shows() {
   grep -q "$1" "$tmp/screen"
}

echo "[no config at all: defaults, saved as htop-gpurc, no stock folder created]"
h=$tmp/fresh; mkdir -p "$h"
run HOME="$h"
check "htop-gpurc written" "[[ -s $h/.config/htop-gpu/htop-gpurc ]]"
check "no ~/.config/htop created" "[[ ! -e $h/.config/htop ]]"

echo "[only stock htoprc: used as the starting point, stock file untouched]"
h=$tmp/seed; mkdir -p "$h/.config/htop"; stock_rc "$h/.config/htop/htoprc"; cp "$h/.config/htop/htoprc" "$tmp/stock.orig"
run HOME="$h"
check "header from stock config" "shows Hostname"
check "htop-gpurc written from it" "grep -qs 'column_meters_0=Hostname' $h/.config/htop-gpu/htop-gpurc"
check "stock htoprc unchanged" "cmp -s $h/.config/htop/htoprc $tmp/stock.orig"

echo "[own htop-gpurc and stock htoprc: own one wins, stock untouched]"
h=$tmp/own; mkdir -p "$h/.config/htop" "$h/.config/htop-gpu"; stock_rc "$h/.config/htop/htoprc"; own_rc "$h/.config/htop-gpu/htop-gpurc"
run HOME="$h"
check "header from htop-gpurc" "shows Uptime && ! shows Hostname"
check "stock htoprc unchanged" "cmp -s $h/.config/htop/htoprc $tmp/stock.orig"

echo "[legacy ~/.htoprc only: used as the starting point and NOT deleted]"
h=$tmp/legacy; mkdir -p "$h"; stock_rc "$h/.htoprc"
run HOME="$h"
check "header from ~/.htoprc" "shows Hostname"
check "~/.htoprc still there and unchanged" "cmp -s $h/.htoprc $tmp/stock.orig"
check "htop-gpurc written" "grep -qs 'column_meters_0=Hostname' $h/.config/htop-gpu/htop-gpurc"

echo "[XDG_CONFIG_HOME set: \$XDG_CONFIG_HOME/htop-gpu/htop-gpurc, seeded from \$XDG_CONFIG_HOME/htop/htoprc]"
h=$tmp/xdghome; x=$tmp/xdg; mkdir -p "$h" "$x/htop"; stock_rc "$x/htop/htoprc"
run HOME="$h" XDG_CONFIG_HOME="$x"
check "header from XDG stock config" "shows Hostname"
check "XDG htop-gpurc written" "grep -qs 'column_meters_0=Hostname' $x/htop-gpu/htop-gpurc"
check "nothing written under HOME" "[[ ! -e $h/.config ]]"

echo "[HTOPRC set: that file only, no htop-gpu folder]"
h=$tmp/env; mkdir -p "$h"; own_rc "$tmp/custom-rc"
env -u XDG_CONFIG_HOME HOME="$h" python3 -I "$here/htop-capture.py" "$tmp/custom-rc" "$htop" 2 > "$tmp/screen"
check "header from \$HTOPRC" "shows Uptime"
check "no htop-gpu folder created" "[[ ! -e $h/.config/htop-gpu ]]"

echo
[[ $fails == 0 ]] && echo "ALL PASSED" || echo "$fails FAILED"
exit $((fails > 0))
