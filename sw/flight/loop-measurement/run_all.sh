#!/bin/bash
# One-command reproduction:  ./run_all.sh      (needs riscv64-unknown-elf-gcc with rv32 multilib, gcc, python3)
# Outputs: build/<cfg>/..., results/summary.md, results/summary.json
set -e
D=$(cd "$(dirname "$0")" && pwd); cd $D
P=${RISCV_PREFIX:-riscv64-unknown-elf}
NITER=${NITER:-2000}
mkdir -p build results

# 1. scenario + generated tables
python3 -I scenario/gen_params.py src/params_gen.inc
python3 -I scenario/gen_scenario.py build/scenario.c $NITER

# 2. simulator + known-answer tests
gcc -O2 -Wall -o build/rvsim tools/rvsim.c
tests/run_kat.sh 2>&1 | grep -v RWX | tee results/kat.txt
grep -q FAIL results/kat.txt && { echo "KAT FAILED"; exit 1; } || true

# 3. host (x86) reference runs of the same sources -> checksums
HF="-std=gnu11 -O2 -ffp-contract=off -DHOST -Isrc -Ibuild"
gcc $HF src/control_step.c src/control_init.c src/harness.c build/scenario.c -o build/host_fixed
gcc $HF -DNUM_FLOAT src/control_step.c src/control_init.c src/harness.c build/scenario.c -o build/host_float
build/host_fixed > results/host_fixed.chk; build/host_float > results/host_float.chk

# 4. target configs:  name | march | opt | numeric | extra defs
CONFIGS=(
 "A|rv32im|-O2|fixed|"
 "B|rv32im|-Os|fixed|"
 "C|rv32i|-O2|fixed|"
 "D|rv32im|-O2|float|"
 "E|rv32imc|-Os|fixed|"
 "F|rv32imc|-O2|fixed|"
 "PA|rv32im|-O2|fixed|-DPROFILE_STAGES"
 "PD|rv32im|-O2|float|-DPROFILE_STAGES"
)
COMMON="-std=gnu11 -mabi=ilp32 -ffreestanding -nostdlib -ffunction-sections -fdata-sections -fstack-usage -Wall -Wextra -Wdouble-promotion -Isrc -Ibuild -DNITER_RUN=$NITER"
for c in "${CONFIGS[@]}"; do
  IFS='|' read NAME ARCH OPT NUMV EXTRA <<< "$c"
  O=build/$NAME; rm -rf $O; mkdir -p $O
  DEF=""; [ $NUMV = float ] && DEF="-DNUM_FLOAT"
  FL="$COMMON -march=$ARCH $OPT $DEF $EXTRA"
  for f in control_step control_init harness sizes; do $P-gcc $FL -c src/$f.c -o $O/$f.o; done
  $P-gcc $FL -c build/scenario.c -o $O/scenario.o
  $P-gcc $FL -c src/crt0.S -o $O/crt0.o
  $P-gcc -march=$ARCH -mabi=ilp32 -nostdlib -Wl,--gc-sections -Wl,--no-warn-rwx-segments -T src/link.ld -o $O/prog.elf $O/crt0.o $O/harness.o $O/control_step.o $O/control_init.o $O/scenario.o -lgcc
  # size probe: link only the loop + libgcc, entry = control_step, so only reachable code is counted
  $P-gcc -march=$ARCH -mabi=ilp32 -nostdlib -Wl,--gc-sections -Wl,--no-warn-rwx-segments -Wl,-e,control_step -T src/link.ld -o $O/loop_only.elf $O/control_step.o -lgcc
  $P-nm -S -n $O/prog.elf > $O/prog.nm
  $P-nm -S -n $O/loop_only.elf > $O/loop_only.nm
  $P-size -A $O/loop_only.elf > $O/loop_only.size
  $P-nm -S $O/sizes.o > $O/sizes.nm
  mv src/*.su $O/ 2>/dev/null || mv *.su $O/ 2>/dev/null || true
  ENTRY=$(awk '$NF=="control_step"{print $1}' $O/prog.nm)
  build/rvsim -e $ENTRY -s $O/prog.nm -o $O/iters.csv $O/prog.elf > $O/sim.out 2> $O/sim.err
  echo "[$NAME] $ARCH $OPT $NUMV $EXTRA : $(tail -1 $O/sim.err)"
done

# 5. branch coverage of the scenario (host, fixed-point) and independent QEMU cross-check of instruction counting
tools/coverage.sh 2>&1 | tee results/coverage.txt
tools/qemu_xcheck.sh 2>&1 | tee results/qemu_xcheck.txt

# 6. aggregate
python3 -I tools/analyze.py
echo "done: see results/summary.md"
