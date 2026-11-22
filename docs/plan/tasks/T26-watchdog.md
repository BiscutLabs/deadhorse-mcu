# T26 Digital watchdog and reset supervision

## Goal

User-assigned continued RTL on main, with D70 reset containment. Implement
the digital watchdog portion of I3 while keeping the external test clocks.
This is not oscillator, sleep/wake, production boot or physical reset signoff.
Neither CI tier runs under the current user instruction.

## Read first

AGENTS; plans03/04/06/07/11–16, STATUS, T20/T22/T24/T25 reports; SoC and
register-map contracts; pinned ClockedPowerReset.scala; shared CDC/reset,
PWM/pinmux and loader interfaces. Skills: task execution, clocked Chisel,
regmap authoring, reference testing, formal properties, timeout triage,
GF180 timing.

## Deliverables and order

1. Reviewed watchdog README/register contract and pinned-source provenance.
2. AON performance/lite watchdog channels, generated owner-checked MMIO,
   immutable active configuration, windowed feed, warning, reset hold and
   POR-retained reset cause/crash counts. Adopt the pinned clocked watchdog's
   count/hold structure; replace its private synchronizer with shared CDC.
3. Opt-in SoC profile extending T25. Performance expiry resets only the
   performance core/client epoch and disables PWM outputs, including PWM
   selected onto GPIO. Shared fabric, DMA and other peripherals survive.
   Lite expiry resets ordinary whole-MCU state. Preserve loader POR lock.
   Main NMI receives synchronized performance warning. No change to earlier
   profiles or ordinary core-reset behavior.
4. Independent deadline-model and MMIO/reset containment tests, actual RTL
   faults, unbounded control properties/covers and negative controls with
   existing 120-second caps. Test asynchronous output disable with main stopped.
5. Fresh GF180 block screen using the existing conservative main-9MHz budget,
   four 8/9MHz × stub/real USB top emissions, source-bound focused receipts,
   independent review and factual report. Full SoC physical timing remains open.

## May change

This brief/index and own STATUS row/log; approved D70 decision record;
hw/ip/watchdog; narrowly required PWM/pinmux output-disable ports; top/map
bindings and focused tests/preparation; affected contracts, ledgers and report.
No vendor edits, other core logic, clock source, memory capacity or test limit.

## Stop conditions

Do not reinterpret T25 loader reset as automatic recovery: a locked image
cannot currently restart after warm reset without a separate boot solution.
Keep that limitation explicit. Stop for a new behavior/architecture conflict,
or proof exhaustion under the existing triage rules. Inherited T23/T25 proof
work is separate and its unapproved helper attempts must not run.
