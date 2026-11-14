#!/bin/bash
# Host gcov branch coverage of control_step.c (fixed-point) under the scenario; lists branch edges never taken.
set -euo pipefail
D=$(cd "$(dirname "$0")/.." && pwd); O=$D/build/cov; mkdir -p $O; cd $O
# These are this runner's generated counters; do not accumulate previous runs.
rm -f -- cov_fixed-*.gcda
gcc -std=gnu11 -O0 --coverage -DHOST -I$D/src -I$D/build $D/src/control_step.c $D/src/control_init.c $D/src/harness.c $D/build/scenario.c -o cov_fixed || exit 1
./cov_fixed > /dev/null; gcov -b -c cov_fixed-control_step.gcda 2>/dev/null | sed -n 2,4p
python3 -I - <<'PY'
import re
cur = None; shown = False
for l in open("control_step.c.gcov"):
    if re.match(r"\s*\S+:\s*\d+:", l): cur = l.rstrip()[:100]; shown = False
    m = re.match(r"branch\s+(\d+) (taken (\d+)|never executed)", l)
    if m and (m.group(2) == "never executed" or m.group(3) == "0"):
        if not shown: print("never-taken edge at:", cur); shown = True
PY
