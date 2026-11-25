# T43 pad receive behavior: approved D110

D110 records user approval on 2026-11-25 of the reviewed proposal below.
D109 selected gf180mcu_fd_io; D110 supplies the explicit driven-pad behavior
exception. Approval alone does not claim implementation or qualification.

The foundry [digital IO control table](https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/digital.html)
marks IE=1/OE=1 as disallowed. The pinned functional model also gates its Y
receiver output with IE. T43 therefore cannot legally keep the input receiver
enabled while the output driver is enabled without further qualified guidance.

The existing [pinmux contract](../../hw/ip/pinmux/README.md) says GPIO input,
edge interrupt and AON wake continue to observe raw GPIO pins while selected
outputs operate. [GPIO input_value](../../hw/ip/gpio/README.md) exposes synchronized
inputs. Substituting the local drive value would mask an externally different
pad level and its edges. D109 did not approve that behavioral change, and T43
forbids changing pin functions silently.

## Approved pad-boundary contract

Apply the following pad-boundary contract, with no peripheral register-map,
GPIO-count or pin-assignment change:

- Released/input mode: OE=0, IE=1; core receives the physical pad receiver Y.
- Output mode: OE=1, IE=0; core receives the local driven I value.
- Open-drain low uses output mode with I=0; released high uses input mode,
  preserving external sampling during ACK/arbitration and clock stretching.
- Input/capture/IRQ/wake paths on a driven pad observe the driven value;
  external contention or an externally different driven-pad level is not sensed.
  Firmware must release the pad to sample an external signal.

Existing timer mode rules already prohibit simultaneous capture and drive on
the same pad. The behavioral exception principally affects GPIO/AON GPIO raw
input observation. Independent review confirmed concrete GPIO tests exercise
external input/IRQ/wake independently while output enable is set, and AON GPIO
tests capture pulses on an output-enabled pin.

This explicitly narrows the raw-input promise while driving. Existing core-port
tests stay unchanged; new chip pad-boundary tests must cover this distinction
(including external forcing), legal enables, open-drain release and pad boot/reset.
USB electrical qualification remains separate. This is a contract, not a claim
that local drive feedback has already been verified for all USB states.

Do not assert disallowed enables, consume spare pads that do not exist, or
connect an unqualified raw pad directly to standard-cell logic.

The explicit approval required by [T43's scope](../plan/tasks/T43-wafer-space-physical-base.md)
and AGENTS.md's behavior-change rule is recorded as D110.
