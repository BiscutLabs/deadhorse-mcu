---
name: "gf180-synth-timing-check"
description: "Use when synthesizing RTL to GF180MCU to measure area or check timing for the Deadhorse MCU: fetching the PDK libraries, running yosys with the slang front end, and applying the per-block timing budget."
---

# GF180 synthesis and timing check (Deadhorse)

Deadhorse's FPGA prototype cannot reveal long paths: a modern FPGA at 12 to 24
MHz has too much slack. Area and timing are judged only against GF180. The
rules are in `docs/plan/14-timing-design-rules.md`.

The **area** flow below was run and reproduced. The **timing** step was not
run when this was written; treat it as a method to confirm.

## 1. Get the cell libraries (verified)

Use the merged liberty files from the pinned PDK release. The liberty files in
the upstream cell-library git repository are stubs that include per-cell
files and will not work.

```sh
bash tools/bootstrap/fetch_gf180_pdk.sh build/pdk
```

It downloads the project cell-library archive from the release tagged
`gf180mcu-792ef67037d74c8c51811eab3ce23cf793491296`, checks its SHA-256 and
unpacks it. Liberty files land at
`build/pdk/gf180mcuD/libs.ref/<library>/lib/<library>__<corner>.lib`.

| Library | Notes |
| --- | --- |
| `gf180mcu_fd_sc_mcu7t5v0` | Has integrated clock-gating cells (`icgtp`, `icgtn`) and scan flip-flops (`sdffq`, `sdffrnq`). The plan's recommended library |

The typical corner is `tt_025C_3v30`. List the `lib/` directory to find the
slow-corner file (slow process, 125 C, 3.0 V) rather than guessing its name.

Network notes: release assets and `git clone` work in restricted sandboxes
where raw-file and archive downloads are refused.

## 2. Synthesize (verified)

```sh
pip install yowasp-yosys==0.71.0.0.post1285
```

This build bundles the slang SystemVerilog front end. Use it for any
SystemVerilog with interfaces, packages or unpacked arrays.

```
read_slang --threads 1 --keep-hierarchy -DSYNTHESIS -I <include dir> --top <top> -G PARAM=value <files...>
hierarchy -top <top>
synth -top <top> -flatten
dfflibmap -liberty <lib>
abc -liberty <lib>
opt_clean -purge
tee -o stat.txt stat -liberty <lib>
```

Run it with `yowasp-yosys -q -l yosys.log script.ys`.

Things that cost time to discover:

| Symptom | Cause and fix |
| --- | --- |
| `thread constructor failed: Not supported` | The WebAssembly build cannot start threads. Add `--threads 1` |
| Assertion about a duplicate identifier during import | Add `--keep-hierarchy` to `read_slang` |
| `Invalid array access` | You used `sv2v` with yosys 0.33. That route cannot read partly indexed unpacked arrays. Use slang |
| `dfflibmap` cannot map a flip-flop, and no cells are listed | The liberty file is a stub or was not found. Use the PDK release files |
| A module with interface ports will not elaborate as top | Write a flat-port wrapper that instantiates the interfaces. |
| The tool cannot open a file under `/tmp` | The WebAssembly sandbox sees the working directory tree. Keep scripts and outputs under it |

For Chisel blocks, emit SystemVerilog with firtool into `build/` and feed it
to the same script. Whether `read_slang` or `read_verilog -sv` suits firtool
output best in this project is not yet confirmed.

## 3. Read the area report (verified)

- Take the **last** `Chip area for top module` line in `stat.txt`. It is the
  total including submodules. Earlier per-module lines are partial.
- Area is in square micrometres. Divide by 1e6 for mm2.
- Count stored bits as the sum of flip-flop cells in the same report.
- This is **mapped** area: no timing constraints, no buffering, no placement.
  The plan converts to placed area by dividing by 0.55.

## 4. Check timing (method; not yet verified here)

1. Map with the slow-corner liberty, not the typical one.
2. Write a constraint file with the block's clock at the project period
   (`clk_main`: 41.6 ns until gate G1 fixes it) and input and output delays.
3. Run a static timing tool (OpenSTA) on the mapped netlist; report the
   worst register-to-register, input-to-register and register-to-output
   paths with their start point, end point and logic depth.
4. **Budget: the worst path must be at most 60 percent of the period.** The
   rest is reserved for wires, clock uncertainty and SRAM timing.
5. Append a row to `docs/ledger/timing.md`.

Prove the flow first on RISCay's clocked design, where it should find a path
of about 120 ns in the elapsed-time logic. If it does not find that path,
the flow is wrong, not the design.

## 5. When a block is over budget

In this order:

1. Read the path. Find which rule in `14-timing-design-rules.md` it breaks:
   unregistered output, a `ready` chain, single-cycle heavy arithmetic,
   logic after a memory, an oversized mux or decode.
2. Fix the structure: register the boundary, add a skid buffer, make the
   operation multi-cycle.
3. Re-run and confirm the path is gone and no new worst path replaced it.
4. Only if the structure cannot change, request a written exception.

Do not raise the budget, lengthen the period, switch to the typical corner or
loosen the constraint to pass. Do not pipeline blocks that already pass.

## Reporting

State for every number: the library, the corner, the tool version
(`yowasp-yosys -V`), the repository commit and the exact command. Say
"mapped, pre-layout, no wire delay". Mark each figure as measured or
estimated. A result that differs from a recorded value by more than 1 percent
is a reason to stop and ask, not to move on.