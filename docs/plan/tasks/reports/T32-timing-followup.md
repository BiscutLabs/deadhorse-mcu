# T32 timing follow-up, 2026-11-23

## Outcome

Done for D80's timing scope: the standalone faithful-core timing failure is
closed by a reproducible, equivalence-checked mapping recipe and frozen fast CI
passes all active checks; the separate SBA reset read-data proof remains
deferred and unproved.

## What changed

- `tools/timing/check.py`: main-9mhz ABC optimization goal is 50000 ps;
  DeadhorsePerfCore at that operating point reloads the freshly emitted
  premapped JSON before mapping. The reload's traversal order is part of the
  measured recipe. All other mapping sequences are retained. No RTL changed.
- `tools/timing/test_timing.py`: optimization-goal expectation updated; the
  independent assertion that 67 ns fails the unchanged 66.666667 ns acceptance
  remains. `tools/timing/README.md` documents the complete recipe.
- `hw/top/reference/measurements/t32/timing_*.py`: reproducible experiments,
  state-cut equivalence, hold/reset diagnostics and historical USB evidence
  derivation. Generated models/netlists/receipts remain under build/.
- D80, STATUS, the debug formal ledger, debug README and T32 report explicitly
  retain the user's proof deferral and distinguish timing from physical signoff.

## Checks run

All execution uses the pinned prefix `python tools/env/run.py run --` on main
at base `9b80375109826e41d28cae95b1b80c653bfc34ff` plus local T32 work.
Exact source, Liberty and artifact hashes are in the receipts.

| Command after pinned prefix | Result |
| --- | --- |
| `python hw/top/reference/measurements/t32/timing_iterations.py --base build/t32/floating-buffer03 --output build/t32/timing-iterations/loop1` | Rejected: measured 70.402451 ns; exact function/graph and wrong-pin/family controls pass |
| `python hw/top/reference/measurements/t32/timing_xor_balance.py --base build/t32/floating-buffer03 --output build/t32/timing-iterations/loop2` | Rejected: measured 73.791389 ns; parity, side-output/graph and wrong-leaf/polarity controls pass |
| `python hw/top/reference/measurements/t32/timing_remap.py` | Loop 3 numerical pass, measured 65.141479 ns; originally unqualified pending equivalence/reproduction |
| `python hw/top/reference/measurements/t32/timing_equivalence.py --candidate build/t32/timing-iterations/loop3/candidate.json --output build/t32/timing-iterations/equivalence02` | `pass`: ABC all-state combinational equivalence and actual wrong-D counterexample |
| `python hw/ip/perf_core/check_top_timing.py --emitted build/t32/final-fast03/fast/faithful-float-emit/asic --operating-point main-9mhz --output build/t32/timing-iterations/standard-flow02` | `PASS DeadhorsePerfCore: RR 65.141479 ns, target 66.666667 ns, failure limit 66.666667 ns; electrical violations 0` |
| `python hw/top/reference/measurements/t32/timing_safety.py --base build/t32/final-fast03/fast/faithful-floating-timing --output build/t32/timing-iterations/safety-original` | Measured baseline hold/reset diagnostics; negative reset-removal retained |
| `python hw/top/reference/measurements/t32/timing_safety.py --base build/t32/timing-iterations/standard-flow02 --output build/t32/timing-iterations/safety-candidate` | Measured candidate hold/reset diagnostics; negative reset-removal retained |
| `python -m unittest tools.timing.test_timing` | `Ran 27 tests ... OK` |
| `python hw/top/reference/measurements/t32/timing_evidence_rebind.py` | `PASS sampling UsbControl`, `PASS sampling UsbEngine`, `PASS sampling Usb`, `PASS packet`, `PASS physical`, `pass`; exact two-file non-USB recipe delta independently reviewed |
| `python tools/ci.py --tier fast --output build/t32/timing-fast01 --usb-evidence build/t32/timing-iterations/usb-evidence/acceptance-manifest.json` | `PASS fast tier active checks; 12 deferred, unproved (see receipt)`; 34 commands pass, measured 3850.781049 s |
| `python tools/check_structure.py --include-untracked` | Exit 0; no output |
| Host `git -c core.safecrlf=false diff --cached --check` | Exit 2: pre-existing blank EOF lines in `basic.tcl`, archived `t32_epoch_fifo.py`, pinned `tc_clk.sv`, and blank context records required by `integration.patch`. Non-passing whitespace diagnostic, not a prescribed CI/T32 acceptance gate; locked vendor/replay bytes preserved and independently reviewed |

The first normal-flow validation, `standard-flow`, retained the old frontend
sequence and still failed at measured 70.203255 ns despite the 50000 ps goal.
This established that JSON reloading, not just the tighter goal, was necessary
to reproduce the trial. `standard-flow02` has a byte-identical mapped JSON to
loop 3 (SHA256 `02c857e1801be732af80c581c924e9b22d798ff28caba4f5cbd2440388606dd4`).
This is validation of the third candidate, not a fourth optimization attempt.

The original mapping proof receipt used ABC's default-zero handling for four
undriven BLIF aliases. It is superseded by `equivalence02`, which exposes all
four matching aliases as arbitrary shared inputs. The stronger proof passes
with no environment assumptions. It matches every original sequential/ICG
cell's identity, type, parameters and attributes, then compares all their
input functions (data, clocks, resets and gate controls) and top outputs.
This is not a proof of the deferred SBA composition property.

The source freeze covers 1598 files in `build/t32/timing-iterations/freeze.json`.
The independent review receipt is `build/t32/timing-iterations/independent-review.json`.
Frozen fast CI freshly reproduces 65.141479 ns and passes all 34 commands,
including USB, faithful-core lockstep and local no-F formal. The four T14/eight
T17 deferrals remain unproved; D80's separate T32 deferral is not a newly passing
CI proof. Only reporting/outcome metadata changed after the frozen run; final
independent publication review verifies that boundary in
`build/t32/timing-iterations/final-review.json`, accepting publication with
the explicit proof/physical debt and staged-whitespace diagnostic. Full tier was not run;
this timing follow-up does not complete an integration-stage exit.

## Numbers

All delays and cell inventories below are **measured**, using the commands
above, pinned Yosys/ABC/OpenSTA and GF180 7t5v0 SS/125 C/3.0 V. These are
mapped pre-layout values without routed wire delay. Budgets are **estimated**
from the unchanged 60% rule, 0.60 * 1000 / 9 = 66.666667 ns.

| Candidate | Worst RR, ns | Area change, um2 | Disposition |
| --- | ---: | ---: | --- |
| Historical frozen fast03 | 70.203255 | Reference | Failed, retained evidence |
| Historical single-buffer carry-in | 70.000366 | +553.1904 | Better but failing diagnostic, used as loops 1/2 input |
| Loop 1: 11 drive-strength changes | 70.402451 | +147.0784 relative to carry-in | Rejected |
| Loop 2: 9 reassociated roots, 118 replacement XOR cells | 73.791389 | +4359.6672 relative to carry-in | Rejected |
| Loop 3 and reproduced standard flow | **65.141479** | +3003.0336 relative to frozen fast03 | Retained mapping recipe; unchanged RTL |

Area changes are **estimated** sums/subtractions of pinned Liberty cell areas.
Loop 3 mapped area is **measured 814013.088 um2** (`loop3/synthesis.log`,
`standard-flow02/synthesis.log`); this standalone-core delta is not a new
whole-SoC area measurement. No chip allowance or area ceiling is changed.
Estimated setup-budget margin: 66.666667 - 65.141479 = 1.525188 ns.

| Validated class | Worst delay, ns | Budget, ns | Start -> end |
| --- | ---: | ---: | --- |
| RR | 65.141479 | 66.666667 | `_63169_/Q` -> `_59757_/D` |
| IR | 32.938839 | 66.666667 | `irq_fast_i[0]` -> `_63027_/D` |
| RO | 49.217548 | 66.666667 | `_63160_/Q` -> `instr_addr_o[30]` |
| IO | 28.060850 | 66.666667 | `irq_fast_i[0]` -> `instr_addr_o[14]` |
| Register -> clock gate | 16.190226 | 66.666667 plus gate setup/hold | `_62019_/Q` -> `core_clock_gate_i.cell_0/E` |
| Input -> clock gate | 14.057454 | 66.666667 plus gate setup/hold | `irq_fast_i[0]` -> `core_clock_gate_i.cell_0/E` |

Worst RR source is instruction-data register bit 30; destination is register-file
bit 574. Measured electrical violations: zero. Minimum measured gate-check
slack: +0.704980 ns. Across 8360 data-hold rows, baseline minimum +0.103031 ns
becomes +0.530017 ns; neither has negative data hold. Reset checks retain the
same minimum removal -0.975158 ns and 1775 negative rows out of 3550 recovery/
removal rows. Raw reset boundary/clock-tree physical qualification remains
T33/T38 work, not a timing-pass claim. The earlier whole-SoC pulse diagnostic
has not been remeasured by this standalone experiment.

Measured mapping equivalence covers 4181 state/clocked cells and 10415 output
functions. The final positive ABC job took 11.988 s; the wrong-D job 1.092 s,
both under the unchanged 120-second cap. No SBA proof job ran.

## Deviations from the brief

D80 explicitly defers the remaining proof and permits three timing iterations
with carry-forward of improvements below acceptance. No numerical limit,
output load, clock period, RTL, assertion or environmental assumption changed.
The optimization-goal test changes a synthesis recipe expectation, not the
separate timing acceptance assertion. No rejected netlist is a production input.

Research basis: the primary [ABC documentation](https://people.eecs.berkeley.edu/~alanmi/abc/abc.htm)
describes mapping and combinational equivalence at register boundaries;
the [ABC balancing paper](https://people.eecs.berkeley.edu/~alanmi/publications/2012/iwls12_del.pdf)
discusses balancing associative logic including XOR. Those methods motivated
diagnostics; only the pinned measurements establish their result here.

## Open issues

- Full tier is not run; this follow-up does not complete an integration-stage exit.
- The original SBA epoch read-data assertion remains deferred and unproved;
  preserve its next proposed BridgeSource payload lemma and prior receipts.
- Physical reset/clock-tree/CTS/pad qualification remains T33/T38 debt.
- PLAN04 USB stopped-clock wake and recovery-loader clock decisions remain
  pending; D80 does not answer them.
