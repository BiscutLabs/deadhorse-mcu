# T02 Flight-loop measurement under CI

## Goal

Make the measurement in `sw/flight/loop-measurement/` a checked part of the
repository: CI reruns it and fails if the recorded numbers change, and its
QEMU cross-check stops being off by one.

## Why

Requirement R-CPU-1 rests on this measurement. It must stay reproducible.

## Read first

- [../../../AGENTS.md](../../../AGENTS.md)
- `sw/flight/loop-measurement/README.md` and `REPORT.md`
- `sw/flight/loop-measurement/run_all.sh`
- `sw/flight/loop-measurement/tools/qemu_xcheck.sh` and `tools/qemu_count.py`

## May change

Files under `sw/flight/loop-measurement/`, `tools/ci.py`,
`.github/workflows/ci.yml`. Do **not** change `src/control_step.c`,
`src/control_init.c`, `src/num_fixed.h`, `src/num_float.h` or anything under
`scenario/`: they define what is measured.

## Known facts

- `./run_all.sh` takes under a minute and needs `riscv64-unknown-elf-gcc`
  (rv32 multilib; measured with Ubuntu's 13.2.0), `gcc`, `python3`.
  On Ubuntu 24.04: `sudo apt-get install -y gcc-riscv64-unknown-elf qemu-system-misc`.
- A clean rerun reproduced `results/summary.json` byte for byte.
- `results/qemu_xcheck.txt` is not stable. `tools/qemu_count.py` infers the
  end of the program from the last traced program counter, so the count
  depends on where QEMU's trace was cut. One run gave four exact matches;
  another gave one match and three results one instruction low.
- `run_all.sh` writes `src/params_gen.inc` into the source directory.

## Steps

1. **Make the QEMU count deterministic.** The end of the measured program
   must come from the program, not from where the log stops. The harness
   ends in `sim_exit()` (`src/harness.c`), which stores to the exit register
   and then spins in `for (;;)`. That spin has no symbol today and the
   function is `static`, so it may be inlined. Give the terminal spin a
   global, non-inlined home (for example a `noinline` function `sim_spin`),
   read its address from `build/<cfg>/prog.nm`, and count traced
   instructions strictly before the first execution at that address. Then
   confirm the simulator's total still equals QEMU's for all four
   configurations. Do not change how `rvsim.c` counts.
2. **Move the generated include** so nothing is written under `src/`: emit
   `params_gen.inc` into `build/` and add `-Ibuild` (already present) so the
   sources still find it. Delete the tracked `src/params_gen.inc`.
3. **Add a check script** `sw/flight/loop-measurement/check.sh` that runs
   `./run_all.sh`, then fails unless `results/summary.json` is byte-identical
   to the committed copy (`git diff --exit-code -- results/summary.json`) and
   every line of `results/qemu_xcheck.txt` after the header ends in `MATCH`.
4. **Wire it into CI.** In `.github/workflows/ci.yml` add a job that
   installs the two apt packages and runs `check.sh`. In `tools/ci.py`, run
   `check.sh` only when `riscv64-unknown-elf-gcc` is on the path, and print
   `SKIP flight-loop (no RISC-V compiler)` otherwise.

## Acceptance checks

```sh
cd sw/flight/loop-measurement
for i in 1 2 3 4 5; do ./run_all.sh >/dev/null && cat results/qemu_xcheck.txt | grep -c MATCH; done   # prints 4 five times
./check.sh                                    # exits 0
git status --short src/                       # no params_gen.inc, nothing modified
grep -c "transition | 2101 | 1851 | 2171" results/summary.md   # 1
python3 ../../../tools/ci.py                  # PASS
```

## Stop and ask

- `results/summary.json` changes after your edits. Per-iteration counts are
  taken inside `control_step` and must not move. If adding the spin function
  shifts whole-program totals in `qemu_xcheck.txt`, that is expected; if it
  shifts anything in `summary.json`, stop.
- The QEMU count still differs after step 1. Report the two counts and the
  trace tail; do not add a tolerance.

## Out of scope

Changing the control loop, adding configurations, cycle-accurate
measurement (that is spike S1).
