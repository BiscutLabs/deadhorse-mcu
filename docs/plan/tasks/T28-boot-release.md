# T28 Lite-first performance-core release

## Goal

Continue the assigned RTL on main without CI. Implement the digital lite-first
release required by plans07/16, using the existing validated recovery START.
Keep external clocks and earlier profiles. This does not implement production
ROM/QSPI boot, calibration loading, sleep control or locked-image warm restart.

## Read first

AGENTS, plan README/STATUS/task index/skills15; plans03/04/06/07/11–14/16;
bus/SoC and recovery-loader contracts; T25/T26/T27 reports; pinned clocked
reset/boot sources, shared ResetRelease, loader START and core/client epoch
interfaces. Skills: task execution, clocked Chisel, regmap, reference testing,
formal properties, timeout triage and GF180 timing.

## Deliverables and order

1. Independently reviewed boot_control README/register contract. New digital
   two-core sequencing is required; retain the adopted loader/cores/reset
   primitives unchanged. No private synchronizer or new clock domain.
2. Lite-owned AON MMIO at power_reset_timer+0x300, size0x100. Record a validated
   START in the whole-reset epoch. Correct full-word RELEASE key after that
   observation opens performance core/client reset monotonically. Repeated
   correct RELEASE is idempotent; wrong key/early command sets error.
3. Whole-reset assertion clears the release asynchronously; AON service reset
   cancels command transport without withdrawing an established release.
   Shared buses, DMA, PWM and other peripherals keep their existing scopes.
   Existing main ResetRelease synchronizes release and actual memory epochReady
   still gates fetch. No stopped-clock permission inferred from demand outputs.
4. Opt-in profile extending T26/T27; real loader/real lite firmware releases
   the performance ROM program. Test initial hold, denied/malformed commands,
   stopped-main release, service resets, reset-interrupted commands and whole
   reset reclosure, with actual negative controls and independent reference.
5. Formal control/owner/reset properties with covers/faults and existing120s
   caps; no inherited proof retries. Fresh mapped GF180 block screen at the
   existing conservative9MHz budget, four8/9MHz × stub/real-USB complete tops,
   frozen focused tests, independent review and report. Neither CI tier runs.

## May change

Own brief/index/STATUS row/log; hw/ip/boot_control; narrow SoC/map/emitter/test
bindings; focused dv/soc firmware/preparation/checks; affected contracts,
ledgers and report. Preserve inherited dirty work, existing profile behavior,
loader programming lock, clock-source choices and acceptance limits.

## Stop conditions

Stop for a new behavior/architecture conflict. Do not bypass the loader lock
or present bootSeen as current lite health. No full I3/I4, physical reset,
analog supply qualification or whole-chip timing claim follows this task.
