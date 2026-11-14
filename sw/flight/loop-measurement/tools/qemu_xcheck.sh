#!/bin/bash
# Independent cross-check of the simulator's *total retired instruction count* against QEMU
# (qemu-system-riscv32 -M virt, one instruction per TB, count executed TBs from the exec log).
# Builds short runs (NITER=40 per mode) of configs A, C, D, E with -DPLAT_QEMU; the very same ELF
# runs in both. Missing tools or incomplete traces are failures.
set -euo pipefail
D=$(cd "$(dirname "$0")/.." && pwd); cd $D
P=${RISCV_PREFIX:-riscv64-unknown-elf}
command -v qemu-system-riscv32 >/dev/null || { echo "qemu-system-riscv32 not installed" >&2; exit 1; }
N=40; mkdir -p build/q; python3 -I scenario/gen_scenario.py build/q/scenario.c $N >/dev/null   # own scenario.h in build/q
echo "config | rvsim retired | QEMU executed insns | match"
for c in "A|rv32im|-O2|" "C|rv32i|-O2|" "D|rv32im|-O2|-DNUM_FLOAT" "E|rv32imc|-Os|"; do
  IFS='|' read NAME ARCH OPT DEF <<< "$c"
  FL="-std=gnu11 -mabi=ilp32 -march=$ARCH $OPT $DEF -ffreestanding -nostdlib -ffunction-sections -fdata-sections -Isrc -Ibuild/q -Ibuild -DNITER_RUN=$N -DPLAT_QEMU"
  O=build/q/$NAME; mkdir -p $O
  for f in control_step control_init harness; do $P-gcc $FL -c src/$f.c -o $O/$f.o; done
  $P-gcc $FL -c build/q/scenario.c -o $O/scenario.o; $P-gcc $FL -c src/crt0.S -o $O/crt0.o
  $P-gcc -march=$ARCH -mabi=ilp32 -nostdlib -Wl,--gc-sections -Wl,--no-warn-rwx-segments -T src/link.ld -o $O/prog.elf $O/crt0.o $O/harness.o $O/control_step.o $O/control_init.o $O/scenario.o -lgcc
  S=$(build/rvsim $O/prog.elf 2>/dev/null | awk '/^TOTAL/{print $2}')
  $P-nm -S -n $O/prog.elf > $O/prog.nm
  Q=$(python3 tools/qemu_trace.py $O/prog.elf $O/prog.nm $O/qemu.log)
  echo "$NAME ($ARCH $OPT $DEF) | $S | $Q | $([ "$S" = "$Q" ] && echo MATCH || echo "DIFF($((Q-S)))")"
  [ "$S" = "$Q" ] || exit 1
done
