# T36 Production boot ROM firmware

## Goal, inputs and readiness

Implement I4 production ROM firmware after T32/T33 completion and alongside T35. Use the
existing lite-first boot release, QSPI command/XIP, UART gateway contract and
frozen I2C recovery loader. Read plan04/07, boot-image formats, D34/D73, T18,
T28–T30 reports and ownership contracts. No signed boot or loader extension.

## Deliverables

1. Reviewed image/manifest ABI: architecture, lengths/ranges, compatibility,
   CRC coverage, entry points, A/B and golden selection and deterministic failure
   policy. CRC detects corruption only. Validate each application image and destination
   before entering that image; trusted ROM execution/release follows the per-core
   sequence below. Avoid overlaps, overflow and unintended owners.
2. Lite boots first and validates calibration/configuration and its own image,
   then releases trusted performance ROM through boot control. The performance
   core validates/copies its own hot image before application entry, preserving
   the existing exclusive performance-SRAM ownership. Cold XIP follows current
   ownership/arbitration. Measure complete ROM and SRAM/stack footprint.
   Before implementation, enumerate the cold-reset instruction source, program
   load path and release/lock transitions: current LiteHart starts only from
   loader START and cannot write its protected program region. Autonomous
   lite-first QSPI boot is not already supplied by these bindings. Review a
   narrow top-level ROM/start selection against the existing map; stop for a
   concrete mapping/ownership decision if needed, without extending the loader.
3. Power-loss-safe A/B update/recovery protocol, keeping a known bootable image;
   golden fallback and serial recovery when no image is usable. UART gateway
   implements the reviewed packet protocol in firmware where feasible; existing
   I2C loader and programming-lock/reset policy are unchanged (D73).
4. ROM build reproducible in pinned toolchain, generated images only in build/.
   State fixed ROM contents and physical implementation requirements for T38.
   Debug halt-on-reset must work without bypassing reset/loader safety.

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

sw/boot and supporting HAL/host image tools, dv/soc boot models/fixtures,
narrow top-level ROM/start binding after the feasibility contract is approved,
image-format docs and own report/ledger.
No new recovery-loader RTL, signed authentication or new peripheral. Stop if
the UART transport needs an unbriefed hardware gateway rather than firmware.

## Task acceptance (unverified)

- `python dv/soc/boot/check.py --output build/t36/boot`: real production ROM,
  QSPI model and serial wires; A/B/golden valid/invalid/CRC/range/compatibility
  cases; interrupts/reset/power-loss at update phases; recovery through UART
  and existing I2C; independent image/parser oracle and bad-CRC/range faults.
- Verify no unvalidated application executes (trusted perf ROM may run before
  its image validation), correct lite release sequencing, correct
  lock/owner boundaries and no stale release across reset. Use formal checks
  for digital handoff contracts and firmware-directed/seeded tests for parsing;
  do not call finite firmware tests an unbounded boot proof.
- Measure ROM bytes, SRAM high-water/stack, boot/recovery time and integrated
  cycles; replace the assumed ROM allowance with actual implementation area.
  Run two-hart JTAG boot interaction and full tier at I4 exit.

## Stop conditions

Stop for loader/lock changes, unsupported ROM capacity, a new image policy or
memory-map conflict, unavailable UART transport, or area/cycle acceptance change.
Do not solve an image-fit problem by silently raising SRAM/ROM capacity.
