# QSPI formal ledger

## T29 — 2026-11-21

**Measured** by pinned `python hw/ip/qspi/formal/check.py --output
build/t29/frozen01/formal`, from `python dv/soc/check_qspi.py --output
build/t29/frozen01`, main HEAD72bcfacc0916b6c00d54f5c4518ab16aa46c5a47 plus
receipt-hashed local changes. Formal receipt PASS. Neither CI tier runs.

| Model | Assertions | Kind | Engine | Measured seconds |
| --- | --- | --- | --- | --- |
| QspiEngine pin/result safety | 8 | proved unbounded | abc pdr | 0.515 |
| Qspi permanently ineligible origins | 2 | proved unbounded | abc pdr | 0.466 |

Only initial reset low is assumed; subsequent reset and inputs are arbitrary.
Engine stimulus maps lengths to0..4 and divider to4..255, representing every
legal wrapper configuration. This construction is part of the proof scope,
not a claim about invalid direct engine inputs. Owner stimulus uses tags2..7,
never eligible for handoff, and does not prove dynamic core ownership.

The five engine covers include both selects, nonzero completed RX, quad output
and released input; the wrapper cover reaches denied response. These finite
BTOR witnesses complete in measured4.320s/0.416s, within128 edges. Actual RTL
faults driving both selects low and bypassing owner admission are rejected
in measured0.416s/0.415s, with concrete witnesses and checked assertion names.
The existing120-second cap remains unchanged.

Completion deadlines, exact CS-high busy/done interval and dynamic0↔1 handoff
have independent simulation and actual fault controls. No unbounded liveness,
full flash model, XIP or physical CDC/reset claim follows from these safety
proofs. See hw/ip/qspi/formal/README.md and the T29 report for full scope.

## T30 native scheduler — 2026-11-21

**Measured** by pinned `python hw/ip/qspi_xip/formal/check.py --output
build/t30/frozen02/formal`, from `python dv/soc/check_xip.py --output
build/t30/frozen02`, main HEAD72bcfacc0916b6c00d54f5c4518ab16aa46c5a47 plus
receipt-hashed local sources. Receipt PASS; neither CI tier ran.

Six interface-scoreboard safety assertions prove unbounded using ABC PDR in
measured 0.466 s: read/command responses have an outstanding owner, error data
is zero, native result is little endian, and read/command result changes occur
only on their respective responses. Initial reset low is the sole assumption;
reset, client traffic, configuration and engine completion/results are arbitrary
thereafter. This conservative engine abstraction does not prove progress.

Four BTOR witnesses reach nonzero native completion, rejected read, command
completion with a native read outstanding, and native completion with a command
outstanding, in measured 0.366 s. Removing the production byte permutation
fails the intended endian assertion with a witness in measured 0.315 s.
Existing caps remain 120 seconds, cover/fault depth 128. Receipt verification
checks exact assertion identity and all model/source/artifact hashes.

The unchanged T29 engine/owner proofs were freshly rerun via
`python hw/ip/qspi/formal/check.py --output build/t30/frozen02/engine-formal`:
eight engine assertions in measured 0.616 s and two permanently-ineligible
owner assertions in 0.466 s, both unbounded; both faults rejected and all covers
reached. Their original stimulus construction and scope remain unchanged.

Native permissions, address fidelity, round-robin progress, reset composition
and real-core boot are directed simulation claims. The frozen focused command
passes measured 37 tests in 11 suites, including actual arbitration-preference
and orphan-response faults. This does not establish unbounded flash liveness,
physical flash compatibility, whole-SoC reset/RDC or production boot policy.
