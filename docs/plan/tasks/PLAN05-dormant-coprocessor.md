# PLAN05 Dormant coprocessor and single-master boot

Queued T41/D103 amendment (not implemented here): consolidate cold, warm,
debug and unchanged USB-transport cohorts. Both watchdogs join warm; causes,
debug and RAM survive warm. Warm ROM validates both images before releasing
lite, skips flash copies only if both match, otherwise reloads. This replaces
the performance-only/surviving-watcher reset contract when T41 lands. Existing
PLAN05 implementation/evidence remains its historical baseline; no USB/analog
interface change or completed proof is implied. See plan10 and the T41 brief.


## Goal and authority

User assignment 2026-11-24, on main. Reshape the lite core into a 32 kHz
always-on radio/sensor watcher, simplify the production chip, and implement
T36 under a single performance-core boot master. No fast AON clock or RAM
power-down. This complete assignment replaces the earlier truncated draft.
Independent review and unchanged numerical limits remain. D91 applies to
iterations inside T36; fast CI is mandatory at both implementation phase ends.

## Read first

AGENTS.md; plans 01, 03, 06, 07, 08, 10, 16; docs/spec/soc.md,
soc-power-reset.md, boot-rom-proposal.md, bus.md, gateway-protocol.md;
hw/top/reference/soc.yaml; D78–D86; reports T18/T21/T22/T25/T28/T33/T35/T36.
Skills: deadhorse-task-execution, clocked-chisel-block-design,
regmap-authoring, reference-model-testing, chisel-formal-properties,
gf180-synth-timing-check, formal-timeout-triage.

## Approved decisions

- E1: performance is the only boot master; no lite ROM. Performance releases
  lite to its program RAM. Supersedes lite-first boot.
- E2: remove the I2C recovery loader, its D1 adoption and D73 freeze; supersede
  D72's production inclusion and D82's loader-specific slow-I2C requirement.
  Recovery is performance-ROM UART plus JTAG. LF AON remains 32 kHz.
- E3: remove lite main-peripheral access and the AON-to-main bridge toMain.
  Keep main-to-AON toAon and mailbox. Main serial controllers are performance-
  owned, including QSPI at reset; amend D7/D24 ownership.
- E4: new lite-owned AON SPI mode 0/3, one CS, programmable divider, small
  TX/RX FIFOs and completion IRQ; at least four AON GPIOs with outputs,
  asynchronous short-pulse edge capture and wake for radio IRQ/power.
- E5: measure watcher code/data/stack; choose the smallest of 2 or 3 KiB
  retained memory that fits with at least 25% margin; derive program/data split.
- E6: replace separate main timers/PWM with a microsecond timebase and three
  general timers, each with shared prescaler/period and four PWM/compare/capture
  channels. Shadow compares apply at period boundaries; channels within one
  timer share frequency. Route twelve channels to existing nine PWM/four timer
  pins through pinmux. Any running channel holds main clock.
- E7: production excludes RVFI; all verification/lockstep builds keep it.
- E8: do not grow main SRAM; measure and compare 16/24/32 KiB options.
- E9: retained memory stays powered in every sleep mode.

## Phase 1 — contracts before RTL

Stop at phase end if its checks fail. Independent review is required before RTL.

1. Update plans01/03/06/07/08/10/16, task index and STATUS. Sleep means WFI with
   oscillator/main services available; dormant means all main holds released,
   oscillator in standby, lite/AON SPI/GPIO on LF. DMA idle, UART TX drained,
   timers stopped, USB disabled per D81. Freeze performance watchdog during
   stopped-main interval and prevent immediate expiry on wake; lite watchdog
   continues. Wake resumes after WFI with retained state, not ROM boot.
2. Update SoC contract and soc.yaml: remove loader/toMain pins/routes/IRQs;
   add AON SPI/GPIO, lite IRQs, merged timers/IRQs, performance QSPI owner and
   lite program-write rule. Run check_soc_map.py; preserve physical pad limits.
3. Add RV32E sw/lite/watcher firmware and independent radio model: GPIO IRQ,
   SPI packet read, address/integrity check, radio power output, mailbox only
   for valid packet. Measure code/data/stack using S3's method and cycles/time
   at 32 kHz. Apply E5 from the measured workload, with provenance/scope.
4. Replace boot proposal with the C contract below and obtain independent review.

## Phase 2 — production RTL, logical commits

5. Remove loader and toMain; make main peripherals/QSPI performance-owned.
   Inventory every removed test with its reason; no silent deletion.
6. Implement hw/ip/aon_spi and hw/ip/aon_gpio, standard layout/YAML/reference
   tests and negative controls. Formal FIFO order, CS framing and wake capture,
   including a pulse shorter than an AON cycle.
7. Performance-owned boot control holds lite reset after whole reset. Program
   writes only from performance while that reset hold is active; release starts
   at program-RAM base. No ordinary lite self-programming.
8. Resize lite retained RAM from E5 measurement.
9. Merge main timers/PWM under hw/ip/timers; retire hw/ip/pwm only after merged
   acceptance. Test every mode/channel, boundary duty updates, timestamp capture,
   any-channel clock hold and a negative control per mode.
10. Remove production RVFI; prove non-RVFI outputs/state equivalent, retaining
    RVFI in every verification/lockstep build.
11. Production dormant test with oscillator actually stopped: each main hold
    blocks entry; invalid radio packet never enables oscillator; valid packet
    mailbox wakes, qualifies oscillator and resumes WFI with SRAM/peripherals
    retained. Performance watchdog neither counts nor fires during dormant or
    immediately on wake; active lite watchdog resets a hung watcher.
12. Measure block/top mapped area and main8MHz/AON32kHz/USB timing; rebuild
    budget and 16/24/32KiB SRAM comparisons. Fixed/hard-float flight has no
    regression. Measure toAon boot-copy and mailbox wake latency. Estimate
    domain leakage from pinned TT25/FF125 cell libraries and SRAM standby,
    resulting dormant current in plan06; state method, no power signoff.

## Phase 3 — T36

Implement revised production ROM and T36's original image/update/power-loss/
malformed/serial-wire cases, plus lite release/program-write and performance-
only-reset tests. Preserve inherited obligations and report deferrals honestly.

## Revised boot contract (C1–C9)

One main ROM at 0x00000000, reset entry0x80. No lite ROM, three-mode sequencer
or cross-core boot handshake. Measure ROM bytes and implementation area.

Whole-chip boot: supply/pin release → running/count-qualified AON → AON released
with lite held reset → external oscillator stable → main released → performance
ROM. Read BOOT_MODE strap (normal or UART wait), then factory directory. Choose
newest fully valid A/B paired performance/lite/configuration bundle, otherwise
golden, otherwise recovery. CRC/compatibility/bounds, commit-last update,
generation-exhaustion rejection and A-wins-ties remain. Copy/verify main image;
copy/verify lite image while held reset; obey lite-start flag (release now or
leave for application); enter performance application.

Only performance may write lite program RAM and only while boot control holds
lite reset. This applies to ROM and application (hold, write, release), replacing
the former ROM-phase seal. Other writes error without effect. Lite cannot write
its own program region. This is integrity, not security; D34/D41 remain.

C4: On performance-only watchdog reset, ROM verifies the performance image
already in SRAM against the same-generation bundle CRC. Skip flash copy when
it matches; otherwise reload that image from flash. Application startup always
reinitializes data/bss. Do not touch lite RAM/reset or stop a running watcher.
If no valid same-generation image can be established, remain in ROM, fail
closed until whole-chip reset. No cross-core negotiation, flash re-selection
or DMA-buffer recovery logic.

C5: A lite-only watchdog reset, if configured, leaves lite held in reset and
notifies performance through mailbox; performance may reload/release. Existing
T33 whole-chip watchdog behavior remains.

C6: UART0 performance-ROM recovery uses gateway v1 framing and its distinct
firmware capability profile, native permissions, reserved staging RAM only,
and explicit command encodings independently reviewed before tests. Enter via
BOOT_MODE or no valid bundle. JTAG is the full fallback. No I2C recovery,
loader-wait mode or runtime loader ownership handoff.

C7: QSPI is performance-owned from reset. Keep the proposal's NOR baseline.
C8: Sleep/deep-sleep wake resumes after WFI with retained state, never ROM.
C9: Retain versioned paired-bundle ABI, lengths, entries, CRCs, directory,
golden, streaming inactive-slot updates and commit-last. Remove lite ROM,
sequencer modes, ROM-copy seal epochs, loader handoff, two-core readiness/
commit handshakes and surviving-lite performance-reset negotiation.

## Acceptance and publication

Run fast CI once at the end of Phase 2 and once at the end of Phase 3; fix
failures before committing/pushing to main. Use relevant tests during iteration;
D91 does not waive either phase-end fast tier. Preserve existing limits and
negative controls except tests explicitly retired with removed functionality.
Record every measurement command/source hash and every estimated/assumed value.
Review contracts before RTL, fixes/evidence before logical commits and push.
Write PLAN05 and T36 reports, keep STATUS authoritative, leave stage/physical
gates open. Stop at each failed phase rather than treating an unfinished check
as passed. Review Phase 1/C, B5, B6, B7, B9, B10 equivalence and B11 independently.

Stop and ask if the watcher cannot transact with the oscillator stopped;
E5 needs more than 3 KiB; a valid packet check exceeds 100 ms at 32 kHz;
lite boot loading exceeds 250 ms; twelve timer channels cannot fit the stated
pin plan; RVFI removal changes any non-RVFI behavior; the area budget is
negative; main misses 8 MHz timing; or boot ROM exceeds its allowance.

Acceptance remains unverified until the phase receipts exist. Report every
deferral explicitly; no automatic proof waiver beyond the approved policy.
