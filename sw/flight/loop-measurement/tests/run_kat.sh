#!/bin/bash
# Known-answer tests for the simulator: RV32IM (no C) and RV32IMC builds.
set -e
D=$(cd "$(dirname "$0")/.." && pwd); B=$D/build/kat; mkdir -p $B
CC=${RISCV_PREFIX:-riscv64-unknown-elf}-gcc
for v in im imc; do
  python3 -I $D/tests/gen_kat.py $B/kat_$v.S $([ $v = imc ] && echo rvc)
  $CC -march=rv32$v -mabi=ilp32 -nostdlib -ffreestanding -T $D/src/link.ld -o $B/kat_$v.elf $B/kat_$v.S
  ${RISCV_PREFIX:-riscv64-unknown-elf}-nm -S -n $B/kat_$v.elf > $B/kat_$v.nm
  ENTRY=$(awk '$NF=="counted"{print $1}' $B/kat_$v.nm)
  $D/build/rvsim -e $ENTRY -o $B/kat_$v.csv $B/kat_$v.elf > $B/kat_$v.out 2> $B/kat_$v.err && R=PASS || R="FAIL(exit $?)"
  echo "KAT rv32$v: $R   $(cat $B/kat_$v.err | tr '\n' ' ')"
  tail -1 $B/kat_$v.csv | awk -F, '{pass=($3==28 && $4==1 && $5==1 && $6==1 && $7==1 && $8==11 && $9==13); print "  counting-window test (expect total 28: mul1 div1 load1 store1 branch11 other13): total="$3" mul="$4" div="$5" load="$6" store="$7" branch="$8" other="$9" -> " (pass?"PASS":"FAIL")}'
  ${RISCV_PREFIX:-riscv64-unknown-elf}-objdump -d $B/kat_$v.elf | awk -F'\t' 'NF>=3 && $2 ~ /^[0-9a-f]+ *$/ {gsub(/ /,"",$2); if (length($2)==4) c++; else if (length($2)==8) n++} END {print "  static encodings in test binary: 16-bit="c+0" 32-bit="n+0}'
done
