# Shared clocked CDC primitives (T14)

Digital qualification: widths 32, 33 and 72 at depth two passed the queue,
reset/Gray, cover and actual-fault checks in `build/t14/cdc-final`; see the
[ledger](../../docs/ledger/bus-formal.md). Other parameters are not covered by
that proof result. All clock domains use these
primitives; no inline synchronizers in consumers. `ResetRelease` asynchronously
asserts and releases after two local rising edges. `CdcSync` has two receiving
flops; Gray vectors only, or single-bit levels, may use it. Stable bundled data
uses the FIFO, never bitwise synchronization.
Standalone `CdcWrite`, `CdcRead` and `CdcSync` require already-qualified local
reset release; the composed FIFO supplies it. The overridable read capture
method exists only to inject a real datapath fault from verification subclasses.

`CdcFifo(width, depth)` has independent write/read clocks, active-low resets,
push/ready and pop/valid interfaces. Either reset flushes both sides; each side
releases synchronously. Depth is a power of two, at least two, at most 32;
baseline two. Capacity includes the registered receive head. The read pointer
advances on consumption, so the sender cannot overwrite the held head. Words
are flop storage; payload flops are not reset because valid/pointers reset.
All public control/data outputs are registers. Startup and synchronization add
cycles, and bubbles are permitted; no throughput claim is made.

`writePending` is a registered sender-side queued-work level for always-on wake
aggregation. It can deassert conservatively after the consumed pointer crosses
back. It does not require a receiving edge to assert. Reset flush is intentional
loss, reported/cancelled by the bus bridge or mailbox outside FIFO reset state.

The physical flow must preserve receiving synchronizer stages and bound Gray
pointer skew to one fastest source period; stable payload paths must settle
before head capture. Multi-clock CDC signoff/MTBF and placement constraints are
later integration obligations. Digital checks assume ideal flop sampling and
do not prove metastability safety. Preliminary storage estimate: depth*width
payload bits plus one width-bit receive head and pointer/synchronizer/control
flops; mapped area is measured separately, not inferred from this estimate.

Proof assumptions and exact proved configurations are recorded in the ledger.
