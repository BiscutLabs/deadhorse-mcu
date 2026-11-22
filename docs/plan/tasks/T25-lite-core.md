# T25 Clocked lite core adoption and AON binding

## Goal

User-assigned continued RTL, 2026-11-21, on main without CI. Adopt the D1
pinned RISCay RV32E core, then add the minimal machine CSR/interrupt/WFI
facilities required by plans03/04 and bind it to the existing AON fabric.
Preserve earlier profiles and unrelated local work. This is digital core
integration, not completion of I3 power control or I4 boot/debug.

## Read first

AGENTS; plans03/04/06/07/11–16 and STATUS; T18/T20/T24 reports; bus/SoC
contracts; pinned ClockedCore, Architecture and independent core oracle;
shared bus/reset interfaces and retained-memory/loader contracts.
Skills: task execution, clocked Chisel, reference testing, formal properties,
formal-timeout-triage and GF180 timing.

## Deliverables and order

1. Reviewed block contract and provenance/license manifest. Import only the
   pinned clocked core and shared ISA definitions needed by it; no async code
   or live upstream build dependency. Establish faithful baseline equivalence
   before adapting its architectural behavior.
2. Registered local-bus adapter: one accepted request and one response,
   stable payload through grant, aligned lane address, preserved byte masks,
   fixed lite origin, common AON service-reset cancellation. A terminal legacy
   Halt notification is local and never becomes a bus transaction.
3. Required machine-mode CSR/trap/interrupt/WFI extension, defined in the
   block contract before implementation. Keep ordinary RV32E execution tied
   to the adopted semantics. Expose retirement/RVFI information for checking;
   do not inherit upstream verification for new logic.
4. Opt-in profile extending T24: loader START/entry launches the actual lite
   core, instruction and data reach existing retained SRAM and AON bus, main
   reset preserves lite execution. Keep external test clocks and current
   performance-core boot behavior. No address aliases; program links at the
   global retained-SRAM base. Old stand-in profiles remain available.
5. Independent architectural and bus tests with seeded stalls, all RV32E
   instruction families, faults/reset, CSR/IRQ/WFI entry/return, and actual
   negative RTL controls. Core-to-mailbox/retained-memory integration through
   the actual loader start path, with reset and ownership tests.
6. Formal bus safety/covers/faults, baseline equivalence, extension control
   properties and RVFI instruction checks, each honestly classified. Preserve
   the existing 120-second job cap and timeout-triage budget.
7. GF180 mapped timing/area using an explicitly reviewed domain timing basis;
   no clock-source selection or acceptance relaxation. Frozen focused tests,
   four whole-top 8/9MHz × stub/real-USB emissions, independent evidence review
   and report. Neither CI tier runs.

## May change

This brief/index, own STATUS row/log; hw/ip/lite_core; necessary top/map/profile
bindings and tests; focused dv/soc preparation/checks and test firmware;
block/SoC contracts, ledgers and report. No vendor edits, other core/peripheral
engine changes, new memory capacity or new clock/reset domain.

## Stop conditions and exclusions

Stop for an unresolved contract conflict, changed acceptance/assumption, or
required behavior beyond the approved minimal core. No privileged breadth
beyond the reviewed minimal machine contract, no alternative core, no async
logic. Debug transport, production ROM/QSPI boot, lite-first performance release,
watchdogs and physical clock gating belong to later briefs. Retain all inherited
T13/T19/T20/T23 proof/timing/physical obligations. Unresolved proofs or unrun
checks prevent full T25 acceptance; staged RTL progress is not task completion.
