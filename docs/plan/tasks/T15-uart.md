# T15: reusable UART peripheral

## Goal

Implement the approved three-UART capability as reusable clocked Chisel IP
and a three-instance bank, without waiting for core performance optimization.
This is peripheral IP, not the gateway, DMA engine or full SoC integration.

## Read first

AGENTS.md; plan 03 architecture, 06 power/clock/reset, 07 peripherals,
11 repository structure, 12 formal, 13 testing and 14 timing; the T14 report;
`docs/spec/bus.md`, `docs/spec/regmap-format.md`, `docs/spec/uart.md`.

Skills: deadhorse-task-execution, regmap-authoring, clocked-chisel-block-design,
reference-model-testing, chisel-formal-properties, gf180-synth-timing-check;
formal-timeout-triage when needed. User direction overrides repeated timeout
triage: retain timed-out obligations as deferred/unproved and continue.

## Inputs and readiness

T05/T07/T09/T14 are available. Reuse RegBlock, BusRegAdapter, LocalBus,
CdcSync and ResetRelease. RISCay has no UART to adopt. User assigned this
brief and implementation on 2026-11-17, deferring performance optimization.
S1 throughput and T13 formal completion are not dependencies of standalone
UART implementation and remain open.

## May change

This brief, task index and own STATUS entry; `docs/spec/uart.md`;
`hw/ip/uart/` including regmap, main/test Scala, formal and timing drivers;
`dv/uart/`; build/CI registration and directly relevant gate tests;
`docs/ledger/uart-formal.md`, timing ledger and `tasks/reports/T15.md`.
No core, FPU, historical firmware or vendor changes. Earlier S1/T13 work is
kept separate from the UART implementation commit.

## Deliverables

1. Review the UART contract before implementing. Generated register decode;
   8N1, inversion, fractional programmable baud, TX/RX FIFOs, sticky errors,
   masked interrupts and DMA request levels. DMA accesses use the checked bus;
   no DMA transfer engine or automatic RX-pop access type is added.
2. Exclusive ownership checks on each accepted bus access using a trusted
   integration-supplied owner. No software-controlled origin spoofing.
3. Run/receive/wake-only/disabled sleep semantics, retained FIFO state,
   clock demand and quiescence. Separate AON wake detector uses shared CDC;
   no generated clocks or asynchronous latches. State the sender preamble
   and integration handshake needed to wake a stopped HF clock.
4. Three independently configured instances with separate bus/pins/IRQ/DMA
   signals; physical addresses and ownership-control wiring remain SoC work.
5. Independent pin/frame and queue tests: arbitrary bytes, consecutive frames,
   inversion, fractional rates, false start/framing/overflow/underflow,
   reset/config/sleep races, ownership denial, byte strobes, FIFO ordering,
   DMA requests, concurrent instances and HF-stopped AON wake. Real negative
   controls must be rejected. At least 921600 baud target at 12/24 MHz and
   the existing 9 MHz trial are checked digitally; analog clock error is
   not thereby qualified.
6. Public-contract formal safety properties with covers and negative controls;
   bounded labels and assumptions explicit. One short attempt per property;
   timeouts deferred, counterexamples investigated. No core ISA sweep.
7. Default T09 GF180 SS timing/area of UART and AON wake modules, including
   generated register interface. Keep the default 24.96 ns block budget.
8. Register the UART regression in fast/full local CI. Independent review,
   report, then commit/push after active checks pass; list all deferrals.

## Acceptance

Interfaces to implement, not pre-existing successful commands:

```sh
python3 hw/ip/uart/check.py --output build/t15/check
python3 tools/ci.py --tier fast --output build/t15/ci-fast
```

The UART check runs register generation, independent simulations, scoped
formal checks and timing with source-bound receipts. A timed-out proof is
reported as `deferred_unproved`, never pass. Such user-authorized deferrals
do not stop unrelated IP work, but must appear in the report and CI receipt.
Full CI is not required this turn; explicitly report it unrun. No area cap
is invented: measure mapped area and distinguish three-instance estimates.

## Stop conditions

Report a real functional counterexample, impossible specified baud/sleep
behavior, or timing failure requiring a contract/limit change. Routine fixes
remain authorized with independent review. Do not silently relax a deadline,
assertion or memory/ownership rule to finish.
