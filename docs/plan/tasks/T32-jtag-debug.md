# T32 Two-hart JTAG debug

## Goal, inputs and readiness

I4 bring-up debug: one JTAG TAP/DTM and one RISC-V External Debug Support
0.13.2 module exposing both harts. Start after PLAN03; T33 can proceed in
parallel against a reviewed wake/reset interface. D41 keeps access unlocked.
Read the pinned Ibex debug interface, LiteCore, shared CDC and current bus-owner
map. No authenticated debug, extra trigger block or permanent lock fuse.

## Choice and deliverables

1. Adopt PULP `riscv-dbg` behind Chisel BlackBoxes, rather than build a new DM.
   Pin a reviewed commit and all transitive files/licenses in
   hw/vendor/riscv_dbg/riscv_dbg.lock.json; include Solderpad and SiFive notices.
   Do not vendor until provenance, synthesis and parameter audit pass. Any
   needed upstream change uses a reviewed lock-file patch, never in-place edits.
2. One module, two distinct hart IDs. Perf uses the existing Ibex debug_req,
   debug mode, halt/exception entry and debug CSR path. Lite receives only the
   minimal precise halt/resume and abstract GPR/PC access it can implement;
   report unsupported commands explicitly. Define stopped/in-flight bus behavior,
   reset priority, architectural state and error reporting before RTL.
3. Provide system bus memory access and halt-on-reset for each hart. Resolve
   bus ownership/arbitration, debug ROM window and reset/sleep handshakes in the
   contract before allocating them; do not silently repurpose a live window.
   Debug traffic must not corrupt a surviving core or bypass transaction safety.
4. TAP runs in TCK; all crossings use the shared CDC primitives. Audit the
   adopted DTM's internal crossing requirements and replace/bind through a
   proved shared-primitive adapter. No unsynchronized shortcut. State supported
   TCK/system rate constraints; handle stopped main and debug wake with T33.
5. Pin OpenOCD source commit/version and build flags in tools/env locks. A
   simulated remote-bitbang endpoint drives actual TAP pins and accesses the
   production top. Acceptance uses OpenOCD, not only direct DMI transactions.

## Read first

AGENTS.md; plan README, STATUS, 03, 06, 07, 08, 10, 11–14 and 16;
docs/spec/soc.md and bus.md; PLAN03 report and the verification-debt register.
Skills: deadhorse-task-execution, clocked-chisel-block-design,
reference-model-testing, chisel-formal-properties, gf180-synth-timing-check,
formal-timeout-triage; regmap-authoring for new registers.

## Shared acceptance and publication (unverified)

All acceptance below is **unverified**. Proposed new checker interfaces are
deliverables to create, not existing or passing tools. Each checker must emit
source/tool hashes, commands, classified results, assumptions, covers and actual
fault controls under build/. No source-text matching tests. Preserve existing
tests, assertions, solver caps, timing budgets and inherited debt.

Integrate in the single production DeadhorseSoc and soc.yaml; no feature
profiles. Use named test fixtures only. Obtain independent contract review before
RTL, then independent implementation/evidence review. Run the fast tier on main
before starting and on the frozen final snapshot, and the full tier if completing
I2, I3, I4 or I5 (D76). Record both tier statuses and all deferrals. Update the task
report and STATUS; commit/push only after required checks/review. Do not tick
this brief's acceptance boxes or a gate.

Pinned invocation prefix: `python tools/env/run.py run --`. Existing checks:
`python hw/top/reference/check_soc_map.py`,
`python tools/check_structure.py --include-untracked`,
`python tools/ci.py --tier fast --output build/<task>/fast`.
Use the reviewed USB evidence interface when required; never skip USB.

## May change

hw/ip/debug, hw/vendor/riscv_dbg, narrow perf/lite debug hooks, shared CDC
adapters, hw/top/reference, dv/soc/debug, sw/boot debug ROM, environment locks,
affected contracts/ledgers and own tracker/report. No core replacement or
unrelated performance/ISA changes.

## Task acceptance (unverified)

- `python dv/soc/debug/check.py --output build/t32/debug`: OpenOCD enumerates
  both harts; independently halt/resume, read/write GPRs and PC, access SRAM by
  SBA, halt on reset, and single-step the perf core exactly one instruction.
  Include invalid hart/command/address, bus error, backpressure, reset during
  request and sleep/wake cases. An actual missing halt binding must fail.
- Prove DMI/SBA exactly-once response, stable outstanding payload, per-hart
  command selection and reset cancellation; list assumptions. Exercise faults
  for wrong hart, duplicate command and stale response. Audit every TCK crossing.
- Rerun core architectural/lockstep tests affected by debug hooks. Measure
  integrated area and per-domain timing including gate/hold/reset checks; replace
  T32's assumed allowance in plan08, and stop if the total exceeds 12.92 mm2.

## Stop conditions and references

Stop for a required ISA/architecture change beyond minimal debug, an unapproved
CDC exception, incompatible upstream license, memory-map conflict, changed
acceptance or unbudgeted area. Do not claim upstream tests prove our bindings.

Primary design references (consulted for this brief):
[PULP implementation](https://github.com/pulp-platform/riscv-dbg),
[Ibex debug interface](https://ibex-core.readthedocs.io/en/stable/03_reference/debug.html),
[OpenOCD source](https://github.com/openocd-org/openocd).
PULP documents execution-based debug and a TCK/system-rate limitation; qualify
the chosen pin, rather than assume arbitrary clock ratios.
