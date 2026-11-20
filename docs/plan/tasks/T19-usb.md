# T19 — Adopt the USB full-speed CDC-ACM peripheral

## Goal

Integrate the USB implementation supplied in `peripherals-ip/USB_FS_CDC`
as a reusable Deadhorse peripheral alongside T15–T18, under D11/D40.
The user assigned this work on 2026-11-18. USB was already approved;
this brief supplies the missing implementation and qualification work.
The optional-chip cutoff and UART/JTAG fallback remain unchanged.

User approval on 2026-11-18 authorizes the suggested selective Chisel
buffer/control conversions and the narrowly scoped vendor-PHY sampler and
decoded/safety-gated output exception in the adoption assessment. No timing,
electrical, protocol or physical qualification limit is waived. Compose the
converted endpoints and retained SIE/PHY in Chisel instead of retaining the
vendor top's hardwired endpoint instances.

## Read first

Read AGENTS.md, the task index and tracker, plans 03, 04, 06, 07, 10–15,
the [bus contract](../../spec/bus.md), the
[gateway protocol](../../spec/gateway-protocol.md), and
`hw/lib/src/main/scala/deadhorse/lib/Cdc.scala`.
Read the supplied USB README, TODO, source/license and PDK I/O audits,
CDC-only top, vendor core/FIFOs/PHY, and executable CDC tests.

**Skills** — deadhorse-task-execution, clocked-chisel-block-design,
regmap-authoring, reference-model-testing, chisel-formal-properties,
gf180-synth-timing-check; formal-timeout-triage for proof budgets.
Use sv-to-chisel-translation if a separately approved conversion is undertaken.

## Inputs and adoption boundary

The supplied directory is a source snapshot, not a Git checkout. Its upstream
`ulixxe/usb_cdc` pin is `6798bf42d43be81368d4e5e2c26b262b41e9fb6a`
(MIT). The supplied `sie.v` contains a disclosed ACK-qualification patch:
do not label it byte-identical to upstream. Capture per-file hashes, preserve
licences, obtain the pristine upstream reference, and represent the delta in
`patches/` before production vendoring. Do not import generated outputs or
depend on files outside this repository at build/test time.

Adopt CDC-ACM only. Composite vendor endpoints, DFU/storage backend, USB host,
high speed and device-initiated remote wake are outside this brief. The missing
host-resume wake detector must be implemented and tested; absence of remote
wake support does not waive D40 host-resume wake.

Recommended boundary: instantiate `usb_cdc` through a Chisel BlackBox with
`USE_APP_CLK=0`, entirely in the USB domain. Use the existing shared `CdcFifo`
for application TX/RX and shared synchronizers/reset release for control.
Do not use the supplied wrapper's private application-clock crossing.
Protocol speed and clock configuration come from the supplied design:
full speed, 12 Mb/s with a 48 MHz sample clock (design requirements, not
measured throughput or timing). Preserve the supplied 64-byte bulk packet
configuration unless a behavior change is approved.

## Deliverables

1. An adoption assessment in `docs/spec/usb-adoption.md`, identifying source
   provenance, license gaps, clock/reset/wake contracts, incompatible structures,
   and the full-versus-selective Chisel conversion recommendation. Measure the
   candidate with the pinned GF180 flow before accepting its physical budget.
2. `hw/vendor/usb/`: pristine source, lock with source hashes and exact patch
   provenance, licences and `.core` file list. New adaptation RTL is Chisel
   under `hw/ip/usb/`, never edits to vendored RTL in place.
3. A reviewed `hw/ip/usb/README.md` contract and an authored `usb.regmap.yaml`
   with a generated register interface: checked gateway/CPU access, TX/RX byte FIFOs,
   status/control, interrupts, defined backpressure/error handling and reset
   flush. Specify arbitration between gateway transport and CPU access before
   allowing concurrent consumers. Reserve offsets inside the existing gateway
   window; do not invent a whole-chip address or bypass gateway permissions.
4. Shared CDC integration and a same-port safe stub under `hw/top/stubs/`.
   No stale bytes survive disconnect, deconfiguration, USB reset or local/peer reset. Provide
   retained pending-work and host-resume wake requests observable by AON while
   the destination clock is stopped. Capture multibit frame/status coherently.
   VBUS loss/reset must disable pad drive and pull-up even with stopped clocks.
5. Independent wire-to-interface tests: enumeration and literal descriptors,
   control requests, bidirectional bulk data, CRC rejection/retry, NAK/ACK
   sequencing, full/empty FIFO backpressure, clocks at differing ratios and
   stopped-clock wake, USB reset/deconfiguration, VBUS loss, local/peer reset,
   ownership rejection, interrupt clearing and stub behavior. Preserve and
   rerun applicable supplied tests; imported success claims are historical.
   Include deliberate data-corruption and reset/wake negative controls.
6. Formal properties beside the Chisel logic: no unauthorized side effects,
   no FIFO loss/duplication outside explicit flush, stable stalled payloads,
   reset/drive safety, and retained wake. Prove the actual byte-width shared
   crossing configuration, with assumptions, reachable covers and negative
   controls. Keep bounded protocol checks distinct from unbounded proofs.
7. GF180 mapped area and path reports for the production USB engine and
   Deadhorse wrapper. Apply the existing 60-percent rule at each real clock
   period; USB uses 60% × (1000/48 ns) = 12.5 ns, an **estimated budget**
   derived from the required sample clock and plan 14's assumed margin.
   No main-clock result establishes USB-clock timing. Physical pad/ESD/VBUS,
   clock-tolerance and board compliance remain explicit qualification work.

## May change

The USB IP/vendor subtree, stub, USB specification, build/CI registration,
USB-focused tests and ledgers, this task's report and tracker row/log.
Planning registration may add this brief to the peripheral plan/task index.
Source assessment may copy candidate inputs under `build/t19/` and use
diagnostic scripts under `scratch/`. Do not modify the external source folder.
Whole-chip gateway, pad-ring, boot/DFU, clock-controller implementation and
unrelated core work are outside this standalone peripheral brief.

## Acceptance

Proposed implementation entry points, **unimplemented/unrun at brief creation**:

```sh
python3 hw/ip/usb/check.py --output build/t19/check
python3 tools/ci.py --tier fast --output build/t19/ci-fast
```

The aggregate must verify provenance/patch reproduction, generated registers,
wire-to-interface tests and fault controls, the formal obligations above,
production emission and GF180 timing. Register it in the fast/full gate using
the existing policy. The default `python3 tools/ci.py` must pass as well.
Write `docs/plan/tasks/reports/T19.md` with exact commands, last output lines,
measurement provenance and unresolved integration/physical limitations.
Independent agent verification is required before completion/commit/push.

## Stop conditions

The source assessment must resolve these concrete conflicts before production
adoption: the supplied packet FIFOs use combinationally selected arrays larger
than plan 14's small-array limit; PHY outputs are combinationally decoded;
PHY input sampling is vendor-local rather than the shared primitive. Do not
silently waive those rules or add input/output cycles that alter USB timing.
Prepare measured evidence and a selective-adaptation or scoped-exception
proposal for explicit approval. Diagnostic measurement does not approve use.

Escalate a required change in packet behavior, CDC/reset/wake guarantees,
USB timing/area limits, uncertain source rights, or the approved optional
cutoff. Missing electrical qualification blocks physical signoff, not digital
assessment. Do not claim completion with outstanding acceptance checks.
