#!/bin/bash
# Bring up RISCay-MCU's toolchain on Linux and run its gates.
# usage: riscay_bootstrap.sh <riscay-mcu checkout> [python-only|full]
#
# Mirrors RISCay-MCU .github/workflows/ci.yml. Verified 2026-11-13 on Ubuntu
# 24.04 x86_64 at RISCay-MCU 4671317:
#   - JDK 21, firtool 1.160.0, sv2v 0.0.13, Icarus 13.0 bootstrap: works
#   - firmware build (event_loop): works, image=728 bytes
#   - Python gate: 513 tests pass, 1 expected skip
#   - Full gate (sbt + Scala suites): NOT verified. It needs Maven Central
#     (repo.maven.apache.org), which was unreachable where this was written.
#
# Prerequisites (apt): python3.12 python3-tk gcc g++ make autoconf gperf bison
#   flex libmpc3 yosys (0.33) git curl
# The interpreter must be Python 3.12 with tkinter. Python 3.13 without
# python3-tk fails at import in several tests.
set -euo pipefail
REPO=$(cd "${1:?path to a RISCay-MCU checkout}" && pwd)
MODE=${2:-python-only}
PY=${PYTHON:-python3.12}
cd "$REPO"
"$PY" -c "import sys, tkinter; assert sys.version_info[:2] == (3, 12), sys.version" \
  || { echo "BOOTSTRAP_PYTHON: need Python 3.12 with tkinter (set PYTHON=...)"; exit 2; }
step() { echo "=== $1 ==="; }

step "pinned chisel-async source"
"$PY" - <<'PY'
import json, os, subprocess
pin = json.load(open('project/chisel-async-source.json'))
if not os.path.isdir('.tools/chisel-async/.git'):
    subprocess.run(['git', 'clone', pin['repository'], '.tools/chisel-async'], check=True)
subprocess.run(['git', 'fetch', 'origin', pin['commit']], cwd='.tools/chisel-async', check=False)
subprocess.run(['git', 'checkout', '--detach', pin['commit']], cwd='.tools/chisel-async', check=True)
PY

step "sv2v (checksum-pinned)"
"$PY" - <<'PY'
import hashlib, json, pathlib, urllib.request, zipfile
dest = pathlib.Path('.tools/formal'); dest.mkdir(parents=True, exist_ok=True)
archive = dest / 'sv2v.zip'
urllib.request.urlretrieve('https://github.com/zachjs/sv2v/releases/download/v0.0.13/sv2v-Linux.zip', archive)
data = zipfile.ZipFile(archive).read('sv2v-Linux/sv2v')
expected = json.load(open('tools/gf180-estimate-inputs.json'))['tools']['sv2v']['sha256']
assert hashlib.sha256(data).hexdigest() == expected, 'SV2V_CHECKSUM'
binary = dest / 'sv2v'; binary.write_bytes(data); binary.chmod(0o755)
PY
export PATH="$REPO/.tools/formal:$PATH"

step "JDK 21 and firtool"
"$PY" .tools/chisel-async/tools/bootstrap_jdk.py
"$PY" .tools/chisel-async/tools/bootstrap.py

step "Icarus Verilog 13.0"
LIB="$REPO/.tools/chisel-async"
if ! "$PY" "$LIB/tools/setup_simulator.py" --output build/simulator-setup; then
  # The library downloads a source archive. Where archive downloads are blocked
  # but git is allowed, build the same pinned revision from a git fetch instead.
  REV=$(sed -n 's/^REVISION = "\(.*\)"/\1/p' "$LIB/tools/build_iverilog.py")
  SRC="$LIB/.tools/iverilog-$REV"; PREFIX="$LIB/.tools/iverilog"
  mkdir -p "$SRC"; cd "$SRC"
  [ -d .git ] || { git init -q .; git remote add origin https://github.com/steveicarus/iverilog; }
  git fetch -q --depth 1 origin "$REV"; git checkout -q FETCH_HEAD
  sh autoconf.sh; ./configure --prefix="$PREFIX"; make -j"$(nproc)"; make install
  cd "$REPO"
  "$PY" "$LIB/tools/setup_simulator.py" --output build/simulator-setup
fi

step "environment"
"$PY" - > build/riscay_env.sh <<'PY'
import json, pathlib
library = pathlib.Path('.tools/chisel-async').resolve()
java = next((library / '.tools/jdk21').rglob('bin/java')).parent.parent
firtool = next((library / '.tools/firtool-1.160.0').rglob('bin/firtool')).parent
print(f'export JAVA_HOME={java}\nexport CHISEL_FIRTOOL_PATH={firtool}')
sim = json.load(open('build/simulator-setup/setup.json'))
for key in ('CA_IVERILOG', 'CA_VVP'):
    print(f'export {key}={sim[key]}')
PY
. build/riscay_env.sh

step "firmware bootstrap"
"$PY" tools/build_firmware.py --bootstrap --app event_loop --output build/ci-bootstrap

STAMP=$(date +%Y%m%d-%H%M%S)
if [ "$MODE" = "python-only" ]; then
  step "Python gate"
  "$PY" tools/ci.py --python-only --output "build/python-$STAMP"
else
  step "full gate (needs Maven Central)"
  "$PY" tools/ci.py --output "build/ci-$STAMP"
fi
step "done"
