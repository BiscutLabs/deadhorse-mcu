# Production SoC physical measurement boundary

The single production `DeadhorseSoc` keeps its RVFI retirement observation ports
for architectural tests, lockstep and debug checking. They are verification
observations, not MCU features or pad signals. The performance core already
permits excluding these observers for physical measurement. No production
feature profile or separate functional RTL is introduced.

The T32 physical measurement projection removes **only** the explicitly
inventoried `rvfi_*` output ports. Every input and every other output remains,
including clock demand, reset/boot handshakes, interrupts, debug and future
controller interfaces. Removing ports solely because they lack a pad is not
permitted. All functional simulation/proof fixtures retain observation ports.

A closed transitive dependency certificate is required: every retained cell's
complete input set (including clock/reset), every retained output and every
retained state transition must be driven only by original inputs or retained
cells. Original retained cells/pins are identical. Explicit keep cells, including
the qualified USB island, remain. A mutation connecting a removed driver to a
retained input must fail. The measurement producer separately checks that
restoring observer ports exactly recovers the instrumented source graph.

The same six synchronous memory model interfaces remain excluded for the pinned
macro/ROM budget; all interfaces are preserved and each cut reverses exactly.
This does not replace ROM firmware or SRAM wrapper qualification.

T32 also measures a reset-tree packing refinement. It retains the existing
GF180 buf_4 cell and maximum fanout eight, with complete bottom-up layers.
Every original connection must resolve to its original driver after collapsing
inserted buffers; CLK/CLKN connections remain exact. Every root/buffer load bound
is checked. Maximum depth cannot increase, and inserted depth is equal for all
original sinks of each root. Cycle and wrong-reset-pin faults must be rejected.
Equal topology depth does not prove analog skew or reset integrity.

Fresh area06 results and the comparison with area04 are in the
[T32 report](../plan/tasks/reports/T32.md). Matched setup/hold, electrical,
gate-enable, reset endpoint and pulse checks accompany the measurement. The
remaining negative raw asynchronous-removal and unbuffered gated-clock pulse
diagnostics stay physical qualification work; the projection is not tape-out
approval. No allowance, utilization, capacity or timing limit changes.

The selected sources are preserved under
`hw/top/reference/measurements/t32/`. T38 must implement and verify the actual
chip boundary and clock/reset trees; a smaller measurement graph alone is not
a pad-ring, routing or physical-fit result.
