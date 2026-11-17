# T17: I2C controller

## Goal

Implement the next standalone serial peripheral: the approved I2C controller
for MS5611/IST8310, 100/400 kHz targets, clock stretching and stuck-bus recovery.
The user assigned this continuation after T16. The separate RISCay I2C loader
is retained by the plan and is not replaced or imported by this task.

## Read first

AGENTS.md; plan README, STATUS, tasks index; plan 02, 03, 04, 06, 07, 11,
12, 13, 14, 15; T16 report; bus and register-map specifications. Write and
independently review `docs/spec/i2c-host.md` before RTL.

Skills: deadhorse-task-execution, regmap-authoring, clocked-chisel-block-design,
reference-model-testing, chisel-formal-properties, gf180-synth-timing-check,
formal-timeout-triage. Existing direction to defer formal timeouts and continue
peripherals applies; preserve every obligation and label it unproved.

## Inputs and readiness

T05/T07/T09/T14/T16 available. Reuse generated RegBlock, BusRegAdapter,
LocalBus, CdcSync and domain-qualified reset. RISCay supplies a target/loader,
not a host controller. No named host RTL exists to adopt. No vendor edits.

## May change

This brief, task index and own STATUS row/log; `docs/spec/i2c-host.md`;
`hw/ip/i2c_host/`; build/CI registration and directly relevant gate tests;
`docs/ledger/i2c-formal.md`, own timing section and task report T17.
No core, FPU, vendor, existing SPI/UART or earlier S1/T13 changes.

## Deliverables

1. Reviewed contract and generated register map; clocked byte-command host
   with START/repeated START, eight-bit WRITE plus sampled ACK, eight-bit READ
   plus selected ACK/NACK, STOP, explicit nine-clock bus clear and finite
   timeout. Open-drain outputs only; shared CDC and digital spike filtering.
2. Independent programmable low/data-hold/high/bus-free timing supporting
   nominal 100/400 kHz targets. Registered output controls, ownership checking
   on every access, sticky status/errors and masked IRQ; retained sleep and
   clock-hold interface. Software sequences complete transfers; no I2C DMA,
   transaction FIFO, target mode or sensor driver is required by this brief.
3. Public-pin independent wired-AND peer tests: address/data ordering, write,
   read, repeated START, final NACK/STOP; stretch and stuck SCL/SDA; recovery;
   arbitration/contention detection; commands/configuration/reset/sleep races,
   strobes/owner denial, receive retention, IRQ and real negative controls.
4. Measure periods and timing minima at assumed 9/12/24 MHz HF for nominal
   100/400 kHz settings; rates must not exceed the nominal mode ceiling and
   remain within five percent below it in the ideal digital pin model.
   Meet Standard/Fast timing minima in that model; physical rise/fall/load,
   oscillator tolerance and pad filtering remain later qualification.
5. Scoped bounded protocol properties and unbounded small ownership/control
   safety where tractable; covers and real faults; all assumptions recorded.
   One 120-second attempt per job; timeouts deferred/unproved, other failures
   diagnosed and repaired without weakening checks.
6. Default T09 GF180 SS timing/area including the register interface, unchanged
   24.96 ns limit, no invented area cap. Register in both CI tiers, run fast
   CI, report/ledgers, independent review, commit and push on acceptance.

## Acceptance

Commands are unverified until run in the pinned environment:

```sh
python3 hw/ip/i2c_host/check.py --output build/t17/check
python3 tools/ci.py --tier fast --output build/t17/ci-fast
```

The aggregate includes generated registers, independent simulation, formal
with covers/faults and source-bound GF180 timing. Retain previous CI jobs and
explicit deferrals. Full CI/ISA sweep is not required for this standalone
peripheral continuation and must be reported unrun.

## Stop conditions

Architecture/contract changes, weakened acceptance or limits, prohibited
imports or genuine impasse after diagnosis and independent review. Do not
claim multi-controller interoperability, physical I2C certification or loader
integration from standalone digital evidence.
