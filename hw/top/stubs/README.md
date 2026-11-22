# Test stubs and inactive pad defaults

Production `DeadhorseSoc` binds every built peripheral under D72. The named
USB-stub test configuration substitutes an error target for USB; production
uses the real USB block. `deadhorse.stubs.UsbStub` is a separate register-block
fixture and is not the production USB implementation.

`SocInactivePads` supplies static safe defaults for the logical pad bundle.
Production overrides QSPI, PWM, GPIO and timer outputs with their real blocks;
their inputs, including IMU DRDY, connect to those blocks. JTAG remains inactive
until its debug implementation. The standalone tie-off fixture does not claim
functional behavior for the peripherals or physical pad cells.

| Signals | Specified width | Standalone inactive default |
| --- | --- | --- |
| QSPI DQ input / output / output enable | 4 each | output and enables zero |
| QSPI SCLK / enable | 1 each | both zero |
| QSPI CS_n / enable | 2 each | selects high; enables zero |
| PWM output / enable | 9 each | both zero |
| JTAG TCK, TMS, TDI | 1 each | ignored |
| JTAG TDO / enable | 1 each | both zero |
| IMU DRDY | 1 | ignored by this fixture |
| GPIO input / output / output enable | 3 each | output and enables zero |
| Timer input / output / output enable | 4 each | output and enables zero |

ADC ports and their dedicated implementation are retired by D74. Their former
pins/window are unassigned. The current allocation is in the
[production SoC contract](../../../docs/spec/soc.md#pins-and-verification-boundary).

Enables are active high. Bidirectional pads have separate input, output and
enable signals; no internal tristate primitive is inferred. Static defaults
are the existing registered-output exception: no state or clock is introduced,
and safe inactive values do not depend on reset or running clocks. This says
nothing about reset behavior of the real peripheral outputs that replace them.
JTAG TCK creates no clock domain in the inactive fixture.

Estimated sequential area of the tie-off fixture is zero flops; physical tie
cells, pad cells and routing are unmeasured. Simulation and the focused formal
runner check unconstrained inputs and actual actuator/GPIO/timer enable faults.
Only the ADC-specific assertion and fault were retired; the other checks remain.
