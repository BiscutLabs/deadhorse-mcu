# T37 manufacturing scan access contract

Draft implementation contract, 2026-11-26. This uses existing shared pads and
the unlocked physical-access policy D41. It does not change normal pin functions,
register maps, memory ownership or functional reset cohorts. Independent review
is required before RTL integration. Numerical protocol constants below are
design choices, not silicon measurements.

## Entry and exit

The tester sets the existing static POR_BYPASS and reset-sampled AON_CLK_SEL
straps high before asserting external reset. OSC_IN and AON_CLK_IN are parked
low. UART1_RX (test reset, active low) is held low. The external reset initializes
the access controller; release it while both functional clock inputs remain
stopped. The existing bootstrap cannot release functional consumers without
AON/source edges. This mode needs neither firmware nor a working analog macro.
Outside bypass mode, on-die cold reset also clears the controller; a normal
POR boot must not rely on the board ever asserting the external reset pin.
Its production reset input is `externalReset_n && coldReset_n`, which reduces
to external reset alone in the required manufacturing setup.

The controller uses the shared two-edge ResetRelease on positive TCK. After
the two release edges, the next 32 positive TCK edges constitute the sole key
window. Hold TMS high and present key `0xD37A6C95`, most significant bit first,
on TDI. TMS high keeps the existing TAP in Test-Logic-Reset. Any mismatch,
missing strap, or high test reset sampled on an edge in this window closes access until
external reset. There is no sliding-window detector and no software entry.
The key is accidental-entry protection, not authentication.
Inputs meet TCK setup/hold; subcycle pulses are not claimed to be detected.

Acceptance arms a dedicated negative-edge TCK register. Persistent test mode
becomes active on the following falling TCK edge, while original/test clock
levels match: ordinary roots low, inverted roots high. The negative-edge mode
flop has its own shared ResetRelease on inverted TCK. The positive-to-negative
arming path has a half-cycle timing obligation. The access controller and its reset-release flops are not scanned;
their exact emitted inventory is reported separately and tested/proved directly.
They are never silently included in a scan coverage denominator.

Test mode remains asserted for shift and capture, independent of scan enable.
No watchdog, scan reset or scan-loaded functional state can clear it. To exit,
hold test reset low, park OSC_IN/AON_CLK_IN/TCK low, and assert external reset.
This clears access and cold-resets the chip under POR_BYPASS. Release external
reset only after normal pin levels/straps and clock sources are restored.
Do not resume functional execution from arbitrary scan-loaded state.

The entry/exit clock parking and static straps are tester requirements. The
controller does not asynchronously sample stopped-clock levels to pretend to
prove them. Test procedures and simulations explicitly exercise this protocol.

## Shared pads

| Manufacturing function | Existing function / physical pad |
| --- | --- |
| Key clock / mode commit | JTAG_TCK / input 3 |
| Key qualifier / serial key | JTAG_TMS / input 4; JTAG_TDI / input 5 |
| Test clock | OSC_IN / dedicated clk |
| Scan enable | UART2_RX / input 8 |
| Test reset_n | UART1_RX / input 7 |
| SI lanes 0–2 | GPIO0–2 / bidirectional 1–3, input only in test |
| SI lanes 3–6 | Timer pins 0–3 / bidirectional 4–7, input only in test |
| SO lanes 0–2 | UART0–2_TX / bidirectional 9–11 |
| SO lanes 3–6 | Timer/PWM outputs 0–3 / bidirectional 25–28 |
| Test-mode acknowledgement | JTAG_TDO / bidirectional 8, high throughout test |

The mapped pre-scan inventory currently has six clock nets and a distinct
negative-edge TAP group. Seven independently driven SI/SO lanes avoid the
false controllability of broadcasting one data input to concurrent chains.
The insertion manifest must bind every lane to its actual original root/edge
and list all registers in order. Unused lanes are tied low. A changed partition
count or ambiguous clock identity is an error, never an implicit exclusion.

## Clock, reset and memory ownership

| Functional group | Test clock at sequential endpoints | Test reset |
| --- | --- | --- |
| Direct OSC_IN, divided main, gated main, AON and positive-edge TCK groups | OSC_IN, with separate chains for each original clock root | UART1_RX |
| Negative-edge TCK TAP state | Inverted OSC_IN into qualified positive-edge scan FFs; original falling-edge grouping retained | UART1_RX |
| Access controller and its release flops | Original TCK, positive/negative edges as above | External reset only |

The root/edge grouping is established before test-clock bypasses are connected.
Every original sequential clock and asynchronous control must be accounted for.
No functional reset generator may reset a downstream scanned FF during shifting
or capture. Test-reset bypasses preserve the original polarity and asynchronous
assertion; functional mode selects the original net exactly. Shared ICG TE is
asserted in test. All mux changes occur under the parked-clock/reset procedure.
Clock pulse, enable, hold and reset-removal checks remain required; a slow shift
frequency alone does not establish hold safety.

Capture is explicitly two-phase: with scan enable low, a rising OSC_IN edge
captures positive groups, followed by a falling edge capturing negative TAP
state using the now-updated positive state. ATPG/replay must model this trace;
it must not treat every capture D as simultaneously observed. Shift also uses
both edges with independent lanes. Initial/final SO samples are associated with
their lane's active edge. No cross-edge chain is constructed.

Every SRAM macro is isolated at its physical interface throughout test mode:
chip enable, global write enable and byte write enables inactive, and macro
read outputs clamped at the digital boundary. Scanned wrapper flops cannot
override isolation. SRAM contents are excluded from logic scan and tested by
the existing March BIST outside scan mode. ATPG sees the actual constant
isolated output, not an independently controllable memory-output cut.

Analog macro controls retain their safe defaults: LF enable high, trim zero,
analog test low; POR threshold safe default zero and analog test low. Neither
analog output is credited as a controllable scan input or test observation.

## Safe output ownership

These clamps are driven by unscanned test mode, never scan enable or scanned
functional state. They persist during capture.

| Outputs | Test-mode value / drive |
| --- | --- |
| OSC_EN | High; tester supplies OSC_IN independently |
| Seven SO pads; acknowledgement | Scan outputs; acknowledgement high, driven |
| Seven SI pads | Input only |
| Remaining PWM/timer outputs | Disabled, output value zero |
| SPI / QSPI clock, data, selects | Output enables off; clock/data zero, selects inactive |
| I2C | Both open-drain drives off |
| USB | TX drive off and pull-up low |
| AON GPIO / remaining GPIO | Output enables off, output value zero |

SO pads are physically shared with application outputs. Manufacturing fixtures
must isolate attached loads before scan entry; this is not an in-system online
test mode. Normal JTAG access is restored only after reset exit.

## Qualification obligations

1. Controller tests and properties: exact finite entry window, wrong key/strap
   rejection, stable mode across capture/reset/watchdog activity, reset exit,
   negative controls and reachable entry. Shared ResetRelease proof is cited,
   not replaced by an assumed reset pipeline.
2. Functional-mode graph/state equivalence: original D/Q/clock/async controls
   preserved; scan FF equations reduce to original with SE=0; test muxes reduce
   to original nets with mode=0. Include changed D/reset-pin negative controls.
3. Actual serial shift/capture/replay with independent SI assignments, both
   edges, chain-break control, safe-pad and SRAM isolation observation. Do not
   substitute a combinational ATPG cut for proof of physical controllability.
4. ATPG reports all logic, scan/control and macro exclusions separately, with
   exact denominators and SAT-untestable vs aborted classification. There is no
   invented S4 target. Transition coverage remains unsupported until qualified.
5. Fresh mapped area and scan timing under this protocol, then T38 follow-up for
   placed hold/routing/fit. The pre-scan fit is not post-scan acceptance.

Physical insertion uses the pinned OpenROAD plus reviewed repository scripts on
generated netlists/ODB. New access RTL is Chisel. No vendor RTL is edited and no
handwritten Verilog test controller is introduced.

Independent contract review (`t43_contract_review`, 2026-11-26) authorizes
controller RTL under this contract. Its required corrections—independent lanes,
polarity-aware parking, two-phase capture, sampled entry inputs, and shared
negative-edge reset release—are incorporated. Whole-chip implementation and
replacement evidence still require separate review.
