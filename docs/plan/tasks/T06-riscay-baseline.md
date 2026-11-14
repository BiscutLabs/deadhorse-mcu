# T06 Bring up RISCay's toolchain and record its baseline

## Goal

On a machine with full network access, run RISCay-MCU's complete fast gate,
export its clocked SoC, and record the baseline numbers Deadhorse's plan
quotes, with the exact commands that produced them.

## Why

Deadhorse builds on RISCay's generator. The plan quotes RISCay's figures
from its documents. Only part of its toolchain was run while planning: the
Scala suites and the clocked export need Maven Central, which was not
reachable. This task closes that gap and tells us whether RISCay is usable
as a dependency (decision D1).

## Read first

- [../../../AGENTS.md](../../../AGENTS.md)
- [../04-riscay-carryover.md](../04-riscay-carryover.md)
- In RISCay-MCU: `README.md`, `docs/build-and-test.md`,
  `docs/desync-contract.md`, `docs/desync-ledger.md`,
  `.github/workflows/ci.yml`
- `tools/bootstrap/riscay_bootstrap.sh` in this repository

## Inputs

- Ubuntu 24.04 x86_64 with network access to GitHub **and**
  `repo.maven.apache.org`. Check first:
  `curl -sI https://repo.maven.apache.org/maven2/ | head -1` must show `200`.
  If it does not, stop: this task cannot be done from that machine.
- `sudo apt-get install -y python3.12 python3-tk gcc g++ make autoconf gperf bison flex libmpc3 yosys git curl`
- RISCay-MCU is public: `git clone https://github.com/BiscutLabs/RISCay-MCU build/riscay-mcu`
  then `git -C build/riscay-mcu checkout 4671317186003740ceb61360ba08c59bbdf10136`.

## May change

New files under `docs/ledger/` and your report. Nothing in the RISCay
checkout except what its own tools write under its `build/` and `.tools/`.

## Steps

1. **Bootstrap and Python gate.**

   ```sh
   bash tools/bootstrap/riscay_bootstrap.sh build/riscay-mcu python-only
   ```

   Expected, verified 2026-11-13: ends with
   `PASS: 513 Python tests; receipt: ...`, one skipped test
   (`test_mounted_drive_hashes_original_windows_file`).
2. **Full gate.** Not verified when this brief was written.

   ```sh
   bash tools/bootstrap/riscay_bootstrap.sh build/riscay-mcu full
   ```

   RISCay's CI allows 60 minutes for a cold run. Record the wall time, the
   number of Scala suites and tests from the receipt, and any failure
   verbatim. RISCay's ledger reports 268 reference Scala tests passing at
   this commit.
3. **Clocked export.** From the RISCay checkout, with the environment from
   `build/riscay_env.sh` loaded:

   ```sh
   . build/riscay_env.sh
   python3.12 tools/sbt.py --bootstrap "clocked/runMain riscay.clocked.EmitClockedSoc build/export/clocked"
   ls build/export/clocked
   ```

   Record the files produced and their sizes.
4. **Reference area.** RISCay's documents give the clocked reference as
   0.5318332992 mm2 mapped with 2,977 architectural bits. Find in
   `docs/build-and-test.md` the command that maps the clocked export
   (`tools/map_clocked.py` or the command the document names) and run it.
   This step was **not verified** and the exact invocation is not known to
   the author of this brief. Record the command you used and the result. If
   the documentation does not give a runnable command, stop and report that;
   do not guess at arguments.
5. **Record.** Write `docs/ledger/riscay-baseline.md` with: the RISCay
   commit; the machine and tool versions (`python3.12 -V`, the JDK, firtool,
   Icarus and yosys version strings printed by the bootstrap); and a table
   of every number you measured beside the value RISCay's documents state,
   each marked *measured* with its command. Where you could not measure
   something, the row says so and why.

## Acceptance checks

```sh
python3 -c "import json,glob; print([json.load(open(f))['status'] for f in glob.glob('build/riscay-mcu/build/*/receipt.json')])"   # every entry is 'pass'
test -f docs/ledger/riscay-baseline.md
grep -c "4671317186003740ceb61360ba08c59bbdf10136" docs/ledger/riscay-baseline.md    # 1 or more
python3 tools/ci.py                                                                  # PASS
git status --short | grep -v "^?? docs/ledger/\|^?? docs/plan/tasks/reports/"        # empty
```

The task is **done** if steps 1 to 3 pass and step 4 either reproduces the
reference area within 0.1 percent or is reported as blocked with the reason.
It is **failed**, and still useful, if the full gate does not pass at this
commit on a clean machine: report exactly which suites fail.

## Stop and ask

- Maven Central is unreachable.
- The full gate fails. Do not try to fix RISCay. Report and stop.
- Any measured number differs from RISCay's documented value.

## Out of scope

The generated (desynchronized) gate, which needs retained timing artifacts
that are not in the repository; any physical flow; any change to RISCay.
