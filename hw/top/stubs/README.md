# Stubs

Explicit stand-ins with final interfaces for deferred integration.

`deadhorse.stubs.UsbStub` retains the T19 register block with its engine
omitted. I1 instead uses its own registered all-access-error USB target, as
required by T20; the two stub meanings are deliberately distinct.

## Inactive I1 pad functions

`SocInactivePads` supplies only the logical pad boundary already named by
T20 and the SoC contract. It implements no peripheral, pin mux or pad cell.
The existing registered error targets still handle the corresponding MMIO
windows; JTAG has no bus master or interrupt connection.

| Signals | Width | Inactive behavior |
| --- | --- | --- |
| QSPI DQ input / output / output enable | 4 each | input ignored; output and enables zero |
| QSPI SCLK / enable | 1 each | both zero |
| QSPI CS_n / enable | 2 each | selects high; enables zero |
| Actuator output / enable | 9 each | both zero |
| JTAG TCK, TMS, TDI | 1 each | ignored |
| JTAG TDO / enable | 1 each | both zero |
| IMU DRDY | 1 | ignored until timer/event capture is briefed |
| GPIO input / output / output enable | 3 each | inputs ignored; output and enables zero |
| Timer capture/compare input / output / output enable | 4 each | inputs ignored; output and enables zero |
| ADC MISO | 1 | ignored |
| ADC SCLK / enable | 1 each | both zero |
| ADC CS_n / enable | 1 each | select high; enable zero |

The I1 top exposes these as `inactive` within its pad bundle, in both USB
variants. Enables are active high. Bidirectional pads use separate input,
output and enable signals; no internal tristate primitive is inferred.

These are static tie-offs, an explicit registered-output exception: no input
affects an output, no state or clock is introduced, and safety does not depend
on reset or a running clock. Actuator outputs therefore stay disabled across
performance-only resets without inventing actuator failsafe behavior. Unused
external inputs are not synchronized because no functional logic consumes them.
JTAG TCK does not create a clock domain in this stub.

Estimated sequential area is zero flops (static constants only); physical
tie cells, pad cells and routing are unmeasured. The requested provisional
contract reserves three GPIO and four shared capture/compare timer pins, plus
the pinned receive-only ADC's MISO/SCLK/CS boundary. See the
[SoC pin contract](../../../docs/spec/soc.md#provisional-gpio-adc-and-timer-pin-contract)
for the estimated 40/10 allocation and reconciliation with the earlier 32/10
estimate. Final pad numbers, alternate functions and physical fit remain open.
No wake, capture, conversion or simultaneous voltage/current acquisition is
implemented or claimed. Existing registered MMIO error targets remain unchanged.

Verification checks the actual tie-off module with unconstrained inputs and
a deliberately enabled actuator output, plus top-level bus/reset simulations.
This establishes safe inactive behavior, not functional peripheral readiness.
