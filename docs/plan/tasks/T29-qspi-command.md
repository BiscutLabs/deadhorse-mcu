# T29 Bounded QSPI command interface

## Goal

Continue assigned RTL on main without CI. Replace the QSPI control stub in an
opt-in profile extending T28, with a bounded, owner-checked command engine.
Plans04/07 replace RISCay GPIO bit-banging; no QSPI RTL exists in that pinned
baseline. XIP, flash arbitration, production boot, flash-part qualification
and throughput qualification remain separate work, not completed by this subset.

## Read first

AGENTS; plan README/STATUS/task index/skills15; plans03/04/06/07/11–14/16;
bus/regmap/SoC contracts; T28 report; shared CDC/reset/register/bus primitives;
SPI host contract/RTL and pinned RISCay flash-boot source inventory.
Skills: task execution, clocked Chisel, regmap, formal properties, reference
testing, GF180 timing and timeout triage.

## Deliverables

1. Independently reviewed README and generated register contract before RTL.
2. Main-clock mode0 command engine with serial opcode, optional single/quad
   address, dummy cycles and single/quad TX/RX data. Registered pins; shared
   input synchronization; bounded frame and full CS-high gap. No held-CS mode.
3. Existing0x40013000/4096-byte control aperture, lite-reset ownership with
   keyed idle-only handoff to either core. Reject denied, invalid, busy and
   partial-key commands; configuration snapshot at START; sticky events.
4. Opt-in T28 extension binding existing QSPI pads, trusted origin, main-service
   reset and main clock demand. Preserve XIP error stub, old profiles, clock
   choices and every other reset scope. No new interrupt or DMA endpoint.
5. Independent wire model, bus/owner/reset tests, main/AON bridge integration
   with reset containment and actual faults. Full-width control/owner formal
   safety and covers, plus bounded frame checks as appropriate; existing120s
   caps and triage rules. No inherited timeout retries.
6. Conservative main9MHz mapped GF180 block screen; four complete8/9MHz ×
   stub/real-USB tops. Frozen focused checks, independent review and report.
   Neither CI tier runs.

## May change

hw/ip/qspi; own brief/index/STATUS row/log; narrow SoC config/map/pad/demand
bindings and tests; dv/soc focused preparation/checks; affected contracts and
ledgers. Preserve inherited dirty work; no vendor edits, flash image ABI,
clock source decisions, new CDC primitive or unrelated peripheral changes.

## Stop conditions

Stop for any substantive contract/architecture conflict, new assumption or
limit change. Report timing failure with path and formal timeouts under the
existing triage budget; do not claim full boot/XIP/physical qualification.
