# T36 Production boot ROM firmware

Queued T41/D103 amendment (not implemented here): consolidate cold, warm,
debug and unchanged USB-transport cohorts. Both watchdogs join warm; causes,
debug and RAM survive warm. Warm ROM validates both images before releasing
lite, skips flash copies only if both match, otherwise reloads. This replaces
the performance-only/surviving-watcher reset contract when T41 lands. Existing
PLAN05 implementation/evidence remains its historical baseline; no USB/analog
interface change or completed proof is implied. See plan10 and the T41 brief.


## Goal, inputs and readiness

Implement the PLAN05 C1-C9 single-performance-master boot contract after the
PLAN05 Phase2 production changes. No lite ROM or I2C recovery loader remains.
Performance ROM loads paired performance/lite/configuration bundles; lite starts
only by explicit performance release. Dormant wake resumes WFI and is not boot.
D34 CRC-only integrity and D41 unlocked debug remain unchanged.

## Deliverables

1. Independently reviewed versioned paired-bundle/directory ABI: lengths,
   ranges, compatibility, CRC coverage, entries, configuration, lite-start flag,
   generation exhaustion and A-wins-ties policy. Validate complete bundles
   before releasing lite or entering an application. Select newest fully valid
   A/B, else golden, else UART recovery. Invalid directory cannot supply a
   guessed golden address. CRC is not authentication.
2. One immutable main ROM in the existing0x00000000 aperture, reset entry0x80.
   Read BOOT_MODE; copy/verify main SRAM and held lite program RAM; obey the
   lite-start flag; enter performance application. Application startup always
   initializes data/bss. No lite ROM, boot handshake or program-write seal.
3. Performance-only reset preserves the running watcher and all lite memory.
   After a bounded stackless drain of surviving DMA/QSPI, validate the retained
   same-generation context and performance SRAM CRC. Skip flash copy if valid,
   otherwise validate/reload only that same image. Never reselect flash slots,
   reset lite, recover DMA buffers or negotiate with the watcher. Fail closed
   until whole-chip reset if the same generation cannot be established.
4. UART0 firmware recovery using gateway v1 COBS/CRC/sequence/duplicate framing
   and reviewed capability/opcode encodings, native-core permissions, reserved
   staging RAM excluding stack/context. Unsupported addresses and reset commands
   error. Stream updates only to the inactive field slot; preserve directory,
   golden and previous usable bundle; verify body/header and program commit last.
   Power loss at every update phase preserves a complete bootable bundle.
5. Reproducible pinned-toolchain build; generated images only under build/.
   Measure ROM content and mapped area against the existing allowance, SRAM
   allocation/high-water/stack, boot/recovery cycles and elapsed time. Keep JTAG
   halt-on-reset and C3 permissions, including direct SBA program-write denial.
   Hand off fixed ROM contents and physical implementation requirements to T38.

## Read first

AGENTS.md; plan README, STATUS,03,06,07,08,10,11-14,16; PLAN05 brief/report;
docs/spec/soc.md, bus.md, gateway-protocol.md, boot-rom-proposal.md and
soc-power-reset.md; T28/T33/T35 reports and verification-debt register.
Skills: deadhorse-task-execution, clocked-chisel-block-design,
reference-model-testing, chisel-formal-properties, gf180-synth-timing-check,
formal-timeout-triage; regmap-authoring for reviewed register additions.

## May change

sw/boot and supporting HAL/host image tools; dv/soc boot models/fixtures;
narrow production ROM/boot-control bindings required by C1-C9; image-format
specification, own report and PLAN05-authorized plan reconciliation. No new
peripheral, loader, signed authentication, memory capacity or ownership policy.

## Acceptance and publication (unverified)

All checks below are unverified deliverables, not claims that tools exist or
pass. Receipts bind source/tool hashes, commands, assumptions, actual fault
controls and classified results. No RTL-source-matching tests. Scoped tests and
short capped proofs during iterations; record deferred costly proofs. PLAN05
requires fast CI on the frozen Phase3 snapshot; full CI is not run under the
user's scoped policy. Do not mark I4 or physical gates complete.

- `python dv/soc/boot/check.py --output build/t36/boot`: actual production ROM,
  independent QSPI NOR peer and UART wires; valid/invalid A/B/golden, CRC,
  bounds/overflow/overlap, compatibility, generation/tie cases, malformed frames,
  duplicates, interrupts/reset/power loss during update phases and stalled transport. Test
  expected firmware capability restrictions, not gateway-origin impersonation.
- Lite held/write/release, leave-held flag, unauthorized program writes,
  instruction-boundary hold/drain, no stale release across reset, no unvalidated application entry, and JTAG
  interaction. Firmware-directed tests are finite tests, not boot proofs.
- Performance-only reset with unchanged/corrupted SRAM, same-generation flash
  valid/missing/corrupt, newer competing slot, running watcher untouched, DMA
  normal drain/permanent stall, and whole-chip reset after fail-closed state.
- CRC/parser oracle and deliberate bad-CRC/range/early-release/commit-order
  controls must fail. Preserve T36 update and power-loss obligations. Explicitly
  retire only former lite-ROM/loader/handoff/seal tests under PLAN05 E1/E2/C9.
- Measure ROM bytes/area, SRAM and stack, boot/recovery time. D88/T39 affected
  core/SoC checks must run through the new ROM/release path with authentic hashes;
  previous loader-based evidence does not qualify this production boot path.
- Independent review of exact ABI/command encodings before tests and of final
  implementation/evidence before acceptance. Run
  `python hw/top/reference/check_soc_map.py`,
  `python tools/check_structure.py --include-untracked`, and Phase3
  `python tools/ci.py --tier fast --output build/plan05/phase3-fast` in the
  pinned environment. Report full-tier status and every deferral.

Write reports/T36.md and update PLAN05 report/STATUS. Commit and push after
required checks and independent review; never tick this brief's boxes/gates.

## Stop conditions

Stop for unsupported ROM capacity/area, a new selection policy or memory-map
conflict, unavailable firmware UART transport, or other PLAN05 stop conditions.
Do not raise memory capacity, tolerance, solver caps or acceptance limits to fit.
