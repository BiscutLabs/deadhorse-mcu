# Oscillator control properties

Implementation in progress. Full PLAN04 formal acceptance is not complete;
the default checker fails closed until full source-clock and gate composition
are included. `--policy-only` is an explicitly partial diagnostic:

```
python tools/env/run.py run -- python hw/ip/osc_ctrl/formal/check.py --policy-only --output build/plan04/formal-policy03
```

The AON policy model asserts: oscillator shutdown follows an acknowledged
stop with no holds and qualified idle; gate request requires observed stability
in the current oscillator epoch; enabled wake pulses survive in pending or
recorded causes; startup fault keeps oscillator on and gate request low; RUN
requests a running clock; reset holds OSC_EN high and gate request low.
ABC PDR is unbounded. BTOR witnesses exercise run,
oscillator-off, wake recording and fault. Deliberately lost wake and refused
gate-open, premature gate-open, ignored-hold and reset-low OSC_EN faults must
fail the named original assertions. Each solver job has
the existing 120-second cap; the 24-edge BMC/cover depth is a witness search,
not a positive proof bound.

Only initial asserted reset is assumed; afterward reset, holds, settings,
wakes and source reports are arbitrary. This policy proof does **not** prove
the reports are truthful or fresh at the physical gate. Source-clock closure,
AON authorization, divider ratio/full pulse widths and reset-high OSC_EN composition
still need separate properties,
covers and negative controls. Simulation exercises some of those behaviors;
it is not a replacement for those proofs or physical RDC/clock qualification.

`divider_check.py --output build/plan04/divider-formal03` proves six source-edge
pulse/progress assertions with ABC PDR, rejects the actual terminal-count fault
and covers a high pulse during reset and a reset-extended low phase. Only the
checker is initialized; DUT phase and functional reset remain arbitrary. After
the first observed transition high phases are exactly three source periods,
reset cannot shorten low phases, and sustained release requires continuing
three-high/three-low operation. This is digital pulse/ratio evidence, not
analog glitch, clock-cell or post-CTS qualification.

`reset_check.py --output build/plan04/reset-formal01` proves digital D83/D84
reset routing, minimum AON release sequencing and frozen AON selection with
ABC PDR, covers both AON strap choices in both bypass modes, and rejects six
actual reset/selection faults. A separate arbitrary-initial-state POR proof
does not assume external reset was asserted. Both AON inputs use one proof
clock: this does not qualify the analog mux or clock switching. POR_BYPASS is
a static elaboration choice; normal and bypass cases exhaust its legal values.

`stability_equivalence.py --output build/plan04/stability-equivalence03` proves
the carry-select decrement against the original full-width arithmetic with
ABC PDR. All output cycles match for arbitrary count, request, oscillatorOn
and reset after initial reset. The wrong-decrement fault fails and a stable
output is reachable. It proves the timing repair, not CDC composition.

Receipt hashes bind exact source/model revisions. Earlier policy receipts
precede later clock-boundary changes included in their broad source seal;
they are historical policy evidence until refreshed on the final snapshot.
They are never full PLAN04 acceptance. All jobs retain the 120-second cap.

Historical `composition_check.py --output build/plan04/composition02` proved
fresh AON qualification before actual main-clock edges, through the production
FIFO, divider, synchronizers and shared ICG. Early-authorization and stale-epoch
faults failed; all covers were reachable. This and the local gate result below
predate the command/completion FIFO repair and do not qualify its current
negative controls or covers. Shutdown closure remains separate.

`clock_contracts_check.py --output build/plan04/clock-contracts01` proved local
gate-closed acknowledgement and count delivery/hold, and rejected their faults.
The full-width no-early-stable assertion timed out, including its alternate
Yices/Z3 portfolio. The aggregate is unresolved, not passed. The later oracle
correction reads the independent count input and requires fresh evidence.
See [the oscillator ledger](../../../../docs/ledger/osc-formal.md) for the
step-0 table and pending helper-invariant proposal. No environmental assumption
or solver cap has changed.

The post-repair shutdown ladder stopped after its three permitted rungs.
With unconstrained startup cutpoints, fresh qualification and OSC_EN on new
main edges are proved; gate-low during OFF and preservation of registered
main holds remain unresolved. The bad-ACK fault failed its intended assertion;
the ignore-source-hold fault timed out. Current real-model covers have not run.
These partial results do not satisfy full formal acceptance; see the ledger
for exact cutpoints, commands and the proposed separately approved helper work.

`reset_causes_check.py` is the separate first attempt for production ResetCauses.
Normal mode takes cold reset from supply reset; bypass takes it from the pin.
Only initial raw cold reset and the static D84 choice restrict DUT inputs;
checkerInit_n initializes cover history only. AON, observation and pin edges
are independent, with clk2fflogic preserving asynchronous pulse capture.
Claims are cold-clear/encoding, capture of pin pulses including between AON
edges, held-brownout capture after three active edges, sticky cause bits and
absence of pin/brownout causes without corresponding raw-source history.
Capture obligations begin after two AON cold-release edges; cold reset takes
priority and clears cause history. Brownout's three active edges begin after
that qualification.
Brownout's holding interval is an antecedent, not an assumption. Covers include
POR, a sub-AON pin pulse, brownout with/without pin history and subsequent cold
clear. The cover-only six-bit epoch cannot wrap in its 24-global-step search.
Normal-mode input faults disconnect pin/cold/brownout or invent pin/brownout
events; bypass's wrong selection fault must fail its encoding checks. Every
solver job keeps the 120-second cap; positive PDR is unbounded.
`--output build/plan04/reset-causes04` passes both positive jobs, six intended
faults and seven covers (measured by the runner on receipt-hashed sources).
The sub-AON cover records a completed pulse while the AON epoch is unchanged,
then requires its later cause capture. Earlier cover formulations allowed a
coincident pin release/AON edge and are not used for that reachability claim.
No count/shutdown helper attempt is included. This dedicated proof postdates
fast02. D86 subsequently permits T33 publication with the difficult proofs
explicitly deferred; it does not make this original formal aggregate pass.
The T33 report records the frozen focused acceptance and independent review.
