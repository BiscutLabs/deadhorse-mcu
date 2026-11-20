# USB adoption assessment

T19 source assessment, 2026-11-18. The user subsequently approved the proposed
selective conversions and narrow PHY structural exception. This is not a timing
exception or completed peripheral qualification. D11/D40 already approve optional
full-speed CDC-ACM. [T19](../plan/tasks/T19-usb.md) now assigns implementation.

## Recommendation

Use a selective Chisel adaptation, not a wholesale language conversion.
Keep useful protocol logic as pinned vendor RTL behind a Chisel BlackBox;
write the Deadhorse register/FIFO, reset, ownership, interrupt and wake boundary
in Chisel. Repair or replace specific control/buffer paths on measured evidence.
A mechanically equivalent port preserves the same long combinational paths.

The initial candidate is `usb_cdc` with `USE_APP_CLK=0`: all vendor logic
uses the USB sample clock, and Deadhorse's shared CDC handles the application
boundary. The supplied `usb_fs_cdc_device` forces the vendor's own application
crossing and is not the recommended wrapper. The existing shared FIFO must be
verified for the actual byte-width configuration, including resets and stopped
clocks; its existing wider-word proof receipts are not automatically USB proof.

## Source and licence

The provided `peripherals-ip/USB_FS_CDC` is a directory snapshot without a Git
revision. Its audit names the MIT upstream `ulixxe/usb_cdc` revision
`6798bf42d43be81368d4e5e2c26b262b41e9fb6a`. The upstream MIT licence is present.
The supplied `sie.v` has an ACK-qualification modification and must be pinned
as such, with a reproducible patch against the pristine upstream pin before
production import. The README's package-local `LICENSE` and parent notices
are absent from this supplied snapshot; do not infer the local wrapper/test
licence from that broken reference.

For assessment only, the vendor RTL was copied under
`build/t19/source-assessment/vendor/`. No external path is used by the
measurement itself. SHA-256 of the supplied inputs:

| File | SHA-256 |
| --- | --- |
| bulk_endp.v | d89e779025b4a0197f3f4e0fdf878ee4848324a3545f602caf8ca4abde94dfaf |
| ctrl_endp.v | dbaed52218867d15388d00fb2b4a42682c02232f1a06009f71294d36451bc732 |
| in_fifo.v | 35b8c7f460541949a74e5dd8a0dc7ed99a04979a5542811beb01f8f95b0b14a8 |
| out_fifo.v | f9c7b074cd4f838bb67c622e4d3c9fbe1f0f3ee9c45d1194a254e5ac3c6214bb |
| phy_rx.v | 3077a06565d11d6f70a2c51dca329e7c6883f39904b8f0c2dd2077e0550e42fe |
| phy_tx.v | d76db337191fc1100b55b3d9f89c544a3dc0bcdecdb1f6a65a5b1d389661af4d |
| sie.v | d865d56240abb9317f2435d72e59cc9a9ee9893249c46db441c2acb21740670e |
| usb_cdc.v | 9357cc844d1d59d25e07e6a78615cf81a9acabbeb4ba3f4203a8d7e52fbbad90 |

## Diagnostic GF180 result

**Measured**, at Deadhorse commit
`a280df4fa17516a2ac8507628a6f12e3c4128895` plus the source hashes above:

```sh
python tools/env/run.py run -- python3 scratch/t19_measure.py
FAIL usb_cdc: 22.356871 ns, budget 12.500000 ns; electrical violations 1350
```

This uses the pinned Yosys 0.71+34 (`e419c4eef`) and OpenSTA 3.2.0,
GF180 `gf180mcu_fd_sc_mcu7t5v0`, SS/125 C/3.0 V, the existing mapping recipe,
input slew and output load. The scratch diagnostic only supplies elaboration
parameters and a USB-clock configuration to the existing timing implementation;
production timing tooling and limits are unchanged. Exact generated commands,
netlist and receipt are under `build/t19/source-assessment/timing-direct/`.
The final diagnostic script SHA-256 is
`9dbbae29384c2ca64f4beb6295956f646573885b34f36afcf17bbfd35176eea5`.
For reproduction, copy the hashed vendor inputs to that repository-local
assessment directory, load `tools.timing.check`, supply the candidate parameters
below as `read_slang -GNAME=value` options to every recorded frontend invocation,
and use a copy of `phys/gf180-ws-1x1/block-timing.json` with only the clock period
changed to `1000/48` ns and provenance annotated. Call `measure` on `usb_cdc`,
clock `clk_i`, retaining all frontend, mapping, path and electrical checks.
The script labels the result diagnostic; it cannot authorize a production pass.

Candidate parameters: one channel, bulk maximum packet size 64 bytes in both
directions, `BIT_SAMPLES=4`, `USE_APP_CLK=0`, `APP_CLK_FREQ=48`, zero VID/PID.
These are design configurations, not throughput measurements or shipping IDs.
The **estimated acceptance budget** is 60% × (1000/48 ns) = 12.5 ns;
the margin is plan 14's existing assumption and 48 MHz is the IP requirement.

**Measured** mapped cell area: 193985.4336 square micrometres, or 0.1939854336
square millimetres by unit conversion. This excludes the new interface/CDC,
pads, placement, clock tree and wiring. It establishes no physical reservation.
The electrical count is the STA report's max-capacitance/slew violation count,
not a count of distinct defective nets or an electrical compliance result.

The worst measured path runs from `u_ctrl_endp.byte_cnt_q[4]` to
`u_ctrl_endp.max_length_q[0]`. Buffer replacement alone is therefore not an
established timing fix. Diagnose EP0 control decode and the remaining path
classes; any multicycle claim needs a sampling/enable property, not an assumed
relaxation because the protocol uses a clock enable. No exception is approved.

## Conflicts and required work

| Finding | Required treatment |
| --- | --- |
| Packet stores contain maximum-packet-size plus one byte: 65 at this configuration, with combinational indexed reads | Plan 14 permits only small combinational arrays. Prefer a selectively adapted clocked Chisel buffer, preserving retry/rollback semantics; do not silently reduce packet size. |
| PHY output pins are decoded combinationally from state | A scoped vendor-PHY exception requires approval and actual timing/electrical qualification; inserting a register blindly changes line timing. |
| PHY has its own D+/D- sampling registers | Resolve its boundary with the shared-CDC rule explicitly. Keep MCU-domain crossings on shared primitives; do not add unanalysed sampling latency. |
| Missing host suspend/resume wake detector | Add clocked Chisel detection and retained wake delivered to ungated AON through shared CDC; prove/test arrival while the destination clock is stopped. Device-initiated remote wake remains outside this task. |
| Vendor bulk FIFOs reset on external/USB reset, not merely on deconfiguration | Define session flush through both vendor and shared queues; clearing only the new queues can retain stale vendor bytes. Review clear-halt/toggle and retry semantics explicitly. |
| `frame_o` and `configured_o` are USB-domain outputs | Use coherent snapshot transfer for frame data and shared synchronization for stable single-bit status. |
| No qualified pad binding, VBUS conditioning or clock source; zero default IDs | Keep physical/board qualification open and supply assigned IDs before deployment. |

## Approved implementation direction

Proceed with selective Chisel adaptation of the packet buffers and measured
timing-critical control, retaining the vendor PHY's sampler and combinational
pin decoding under an explicit, narrowly scoped design-rule exception.
That exception would not relax the USB timing budget, electrical checks,
protocol behavior, physical qualification, or shared MCU-domain CDC requirements.
It would allow the PHY candidate to be qualified without assuming that extra
input/output pipeline stages preserve protocol timing.

The user approved this selective direction on 2026-11-18: "okay do the
conversions you suggested, and tackle T19". A full USB/PHY rewrite is not
required. The narrow structural exception does not approve timing closure or
electrical signoff.

An independent agent reviewed the boundary, timing scripts, receipts and mapped
paths. The subsequent T19 implementation imports the pristine locked SIE/PHY,
reproduces the disclosed patch, converts EP0 and packet buffers to Chisel, and
adds the shared-CDC/MMIO/reset/wake boundary and optional stub. Independent
wire/MMIO simulations pass, and selected formal properties are proved; packet
proofs and timing closure remain unresolved. See the [current report](../plan/tasks/reports/T19.md)
and [pending timing decision](usb-timing-decision.md). No complete USB or CI
acceptance is claimed.
