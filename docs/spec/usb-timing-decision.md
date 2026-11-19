# USB SIE timing decision proposal

Status: proposed, not approved or applied. Existing acceptance remains 12.5 ns.

The selective Chisel conversion retains the supplied SIE/PHY. The production
engine measurement under `build/t19/timing-08/engine/result.json` reports
**measured** 21.309978 ns from `sie.data_q[1]` to `sie.out_toggle_q[1]`, with
zero reported maximum-slew/capacitance violations. Command:

```sh
python3 scratch/t19_timing08.py
```

That driver invokes `tools/timing/check.py` on emitted `UsbEngine` and the
locked, patched SIE/PHY with `--operating-point usb-48mhz`. The receipt contains
source hashes and the mapped path. Git baseline is
`a280df4fa17516a2ac8507628a6f12e3c4128895`, plus the uncommitted T19 sources
identified by those hashes. Later source changes require a fresh measurement.

The latest measured `emit-13` engine is 20.556009 ns with zero reported
electrical violations (`build/t19/timing-13/engine/result.json`), using
`python3 hw/ip/usb/timing.py --emitted build/t19/emit-13 --output build/t19/timing-13
--block control --block engine`. The retained SIE data-to-toggle path still
fails. EP0 separately measures 13.042828 ns and also fails the full-rate
12.5 ns budget. This proposal does not waive or resolve that EP0 failure,
packet-buffer proofs, pipeline sampling equivalence or full wrapper timing.

Both ends advance on the same protocol enable, once per four sample clocks.
The production Chisel divider has an unbounded cadence proof and a rejected
early-enable fault (`build/t19/formal-02/cadence/`). A separate Yosys SAT proof
establishes that every retained SIE protocol-register enable implies
`clk_gate_i`, for arbitrary register values and arbitrary PHY outputs:

```sh
python3 hw/ip/usb/formal/sie_enable.py --output build/t19/sie-enable-02
```

This proof checks the actual prepared vendor netlist and rejects a deliberately
always-enabled register. It records the shared internal asynchronous reset
`rstn`; it does **not** establish reset recovery, mapped pin membership, or
authorize a timing exception. PHY register timing is excluded from this
certificate and remains at the sample-clock budget.

## Decision requested

Authorize implementing and accepting a **proved four-edge multicycle class
only between certified SIE protocol-register launch and capture pins**.
Its estimated delay budget would be 0.60 × 4 × (1000/48 ns) = 50 ns.
The 60-percent margin remains the existing plan assumption. This would not
change the sample clock, USB line rate, packet behavior or electrical limits.

Before accepting any such path, the implementation must:

- Bind the cadence and enable certificates to the exact production source and
  mapped register identities, rejecting missing, mixed or ambiguous aliases.
- Prove destination sampling validity across reset/release as well as normal
  operation; no early capture may rely on the exception.
- Partition every register path into certified-to-certified,
  certified-to-full-rate, full-rate-to-certified and full-rate-to-full-rate.
  Only the first class receives the extended budget. All input/output, PHY,
  reset, CDC and Chisel pipeline paths retain their applicable existing limits.
- Declare setup-four and corresponding hold-three constraints; retain
  electrical, clock, reset and short-path checks.
- Reject deliberate premature enables, incorrect pin classification and
  over-budget paths in each class. Obtain independent review.

The alternative is to retain the uniform 12.5 ns SIE budget and undertake a
separately scoped conversion/restructuring of the SIE protocol logic. The
current user approval covers endpoint/control buffers and the PHY structural
exception, not this additional conversion or multicycle acceptance.

Plan 14 says: “A path over budget needs a written entry in the block README
naming the path and why, and approval.” It also requires multicycle constraints
and a property proving valid destination sampling. This proposal requests
that decision; the measurements and preliminary certificates are not a waiver.
