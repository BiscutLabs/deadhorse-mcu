# Production pad wrapper

The single production wrapper is the T43/D105 pinned wafer.space `chip_top`
prepared by [prepare_chip.py](../../../phys/gf180-ws-1x1/prepare_chip.py).
Its [chip_core socket](../../../phys/gf180-ws-1x1/chip_core.sv) binds
DeadhorseSoc and the [indexed pad map](../../../phys/gf180-ws-1x1/pad-map.yaml).
There is no second wrapper or production feature configuration here.

T38/D112 measures the pre-scan chip using the authenticated production mapped
graph, preserving the USB timing certificate and restoring the real LF/POR
macro sockets. Generated netlists, constraints, layouts and receipts live in
`build/t38/`. Scan, analog electrical qualification and full signoff remain
separate obligations; preliminary placement or routing is not tape-out approval.
