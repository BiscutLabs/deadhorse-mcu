# T38 pre-scan physical measurement

D112 authorizes physical data before T37 and defers the broad verification
campaign. No RTL, pad assignment, memory capacity, timing limit or signoff
gate changes. The T43 template/PDK locks and actual LF/POR/SRAM views apply.
The user's follow-up narrows this run to a basic layout/fit study. Stop after
placement and already-completed CTS; routing, DRC and production-GDS work are
deferred. This supersedes the earlier intention to collect routed timing now.

## Netlist boundary

`tools/physical/chip_prepare.py` consumes the authenticated production map and
T43 pad elaboration. Fresh production emission must match the original mapped
inputs byte for byte. Restore LF/POR through named canonical analog ports,
validate their exact interface/control inventory, and recover the original
digital graph by removing that restoration. Synthesize only pad glue.
Audit every retained cell, parameter, pin and bijective net correspondence;
missing-cell, wrong-data-pin and swapped-analog-output faults must be rejected.
Keep all eight internal status observations. There is one production wrapper.

The template's logical common VDD/DVDD and VSS/DVSS aliases may be normalized
to the physical VDD/VSS names. Only typed supply terminals and the four named
supply boundaries move; the complete signal-terminal graph must be identical.
This is D109's existing common-supply contract, not a new power domain.

## Clocks and constraints

Nominal rates are assumed from the production contract: OSC/USB48MHz at the
dedicated clock pad, main generated divide-by-six (8MHz), AON32kHz from either
the LF macro clock pin or fallback input pad, and TCK100kHz. Analyze both
frozen AON mux selections separately. Actual pad arcs remain in the graph.
No asynchronous clock groups or blanket false paths are added. Raw CDC and
RDC violations remain diagnostic until their endpoint qualifications close.

USB setup4/hold3 and setup3/hold2 statements come from the authenticated
production timing receipt, rebound through the audited mapped correspondence.
All original cells are retained. Physical buffering requires reconnecting load
pins, which OpenDB cell locks also forbid; post-stage graph audits therefore
enforce identity/connectivity instead of those locks. Buffer removal and gate
cloning are disabled. Drive-size and equivalent buffer/delay-buffer substitutions
must have identical pin functions
and sequential semantics in every pinned cell-library view. Physical insertion
still needs graph/clock coverage checks. Strict full-rate/pre-enable and ordinary USB warning budgets remain
unchanged. Class delay budgets and full-period setup slack are separate results.

Retain template assumptions of0.25ns clock uncertainty,5% early/late derating,
0.15ns external clock transition, and72.91fF external pad loading. LF transition
is an assumed2.6ns diagnostic value, informed by the limited T43 slew experiment;
it is not a characterized macro arc or a qualified PVT/loading envelope.
The max-transition screen remains3ns. These values are assumptions, not measured
board loading, oscillator jitter or electrical signoff.

External inputs use an assumed0..1ns arrival range from their reference edge.
Output timing assumes an external peer capture requirement of1ns setup and0ns
hold, including board/package propagation. This separates the already-present
pad Liberty arcs from the historical standalone USB pad-plus-board estimate.
Asynchronous inputs retain zero minimum arrival: no phase guarantee is inferred.
Alternate main/AON pads receive both references. These IO rows are diagnostic;
actual UART/SPI/QSPI/USB and board contracts remain qualification work. Internal
bus/reset paths use the actual upstream registers and wires, not port-delay
substitutes. POR remains an asynchronous macro boundary without invented arcs.

## Scope of the result

This run measures the placed, electrically repaired, clock-tree-built design.
No post-CTS optimization, routing, extraction or DRC is required for this scoped
fit result. Cross-domain timing remains unqualified. The layout drawing comes
from actual instance bounding boxes. Area sums and geometric utilization do not
establish routability or replace the future scan-inclusive physical budget.

Report each completed physical stage, cell/macro area, utilization, routing
congestion, setup/hold, gate, pulse, recovery/removal and electrical diagnostics.
Retain failed attempts and exact commands/hashes. No extracted-wire claim may
be made from placement-estimated parasitics. Scan, full analog extraction/PVT,
final equivalence, complete CDC/RDC/MTBF, pad electrical tests, IR/EM, foundry
DRC/LVS/antenna, broad regressions and fast/full CI remain deferred. Router DRC
or a completed flow is not tape-out signoff.
