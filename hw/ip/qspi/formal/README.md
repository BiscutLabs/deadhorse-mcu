# QSPI formal scope

`python tools/env/run.py run -- python hw/ip/qspi/formal/check.py --output build/t29/<fresh-directory>`
emits production engine and wrapper harnesses. Every job retains the existing
120-second cap. Positive safety uses unbounded ABC PDR; covers and faults use
BTOR witnesses within128 edges. No CI or inherited proof retry runs here.

QspiFormal checks eight safety assertions: legal exclusive chip select, clock
low while deselected, selected implies busy/enabled, safe idle, done implies
idle/deselected, result changes only at done, data/direction stability during
SCLK high, and selected CS stability throughout a frame. Five covers reach
both selects, nonzero received completion, quad output and released input.
The negative control drives both selects active and must fail the exclusive
select assertion.

Only reset initially low is assumed; reset, START, data and settings may vary
arbitrarily thereafter. Input construction maps lengths above4 to4 and
dividers below4 to4, preserving all legal engine configurations, as the
wrapper's validation requires. All other fields retain full production widths.
This proves sampled digital safety, not analog input coherence or completion.

QspiOwnerFormal drives every permanently ineligible origin2..7 (0/1 inputs map
to2), without assumptions on bus sequencing. It proves pads remain disabled
and every response errors; a real owner-check bypass must fail. This does not
prove dynamic0↔1 transfer. QspiOwnerSpec separately checks back-to-back handoff
responses, all eight origin tags after each handoff, preserved data and an
actual former-owner-access fault.

Wire simulation checks opcode/address/data against an independent symbol
stream, serial/quad directions and shared-synchronizer sampling. Completion
is bounded directed evidence measured in actual main edges, not a formal
liveness claim. QspiEngineSpec checks exact CS hold/gap and busy/done on public
engine ports, including the largest command/divider and a shortened-gap fault.
Reset/pads, physical sampling, flash part compatibility and complete boot/XIP
remain separate qualifications. Exact receipts/results belong in the T29 report.
