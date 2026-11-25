# AON SPI formal scope

`python hw/ip/aon_spi/formal/check.py --output build/plan05/aon-spi-formal-N`
uses the actual production RTL with formal-only independent shift queues.
Properties cover FIFO capacity/order and CS consistency with start/completion.
Exact serial edges/data are independently tested in simulation. Assumptions:
initial reset asserted, arbitrary reset thereafter, arbitrary LocalBus and MISO,
one AON clock. No bus-stability or software sequencing assumption.

The single positive ABC PDR attempt at120seconds timed out (receipt
`build/plan05/aon-spi-formal01`); it remains unproved. Bounded TX-index, RX-index
and frame faults were rejected; all three covers reached. No unchanged rerun.
Step0 and remaining proof debt are recorded in the PLAN05 report. User-approved
minimal-proof policy defers further decomposition, without marking it proved.
