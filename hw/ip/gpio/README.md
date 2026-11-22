# GPIO and AON wake (T21)

Three dedicated GPIOs; generated 256-byte register window at the existing
0x40012000 base. Owner is integration supplied (performance origin1 in the
functional profile). GPIO data/enables and bus/register state use main clock
and main service reset. Inputs are independent bits synchronized through
CdcSync, not an atomic external parallel bus. Outputs and enables reset zero.

AON wake has its own synchronized inputs and registered sticky request. Its
mask/polarity and clear commands cross as one coherent CdcFifo packet. Only
one command is outstanding; a returned AON acknowledgement must match its
sequence before busy/clockHold clears. APPLY/clear while busy or transport
unavailable sets command_error; no command is silently queued or overwritten.
Either service reset flushes wake transport, mask, acknowledgement and pending
wake. AON reset does not reset main GPIO outputs/events. Configuration must be
reapplied after either wake-domain reset. A level still active wins clearing;
APPLY and CLEAR together test the newly applied mask/polarity. Wake does not
depend on main clock edges after arming. Pulses shorter than AON sampling are
not promised; no latch or pulse stretcher is introduced.
For digital tests, hold an input for at least three sampling edges of the
receiving clock after arming; shorter pulses may be missed. This is not an
analog metastability bound. command_error is polling-only (IRQ bit3 is wake).
The source sequence/busy state and ACK synchronizers share the joint wake
reset. Commands wait for synchronized readiness from both FIFO sides.

| Offset | Register | Meaning / reset |
| --- | --- | --- |
| 0x00 | output_value | rw bits2:0, reset0 |
| 0x04 | output_enable | rw bits2:0, reset0 |
| 0x08 | input_value | ro synchronized inputs |
| 0x0c | rise_enable | rw bits2:0, reset0 |
| 0x10 | fall_enable | rw bits2:0, reset0 |
| 0x14 | events | w1c edge bits2:0, command_error bit3; set wins |
| 0x18 | irq_enable | rw event bits2:0 and wake bit3, reset0 |
| 0x1c | wake_mask | rw bits2:0 shadow, reset0 |
| 0x20 | wake_polarity | rw bits2:0 shadow, 1=active-high, reset0 |
| 0x24 | command | w1p APPLY bit0, CLEAR_WAKE bit1 |
| 0x28 | status | ro wake busy0, AON armed1, wake pending2, transport ready3 |

IRQ is a registered masked event/wake level. Quiescent/clockHold describe
wake-command completion, not permission to discard accepted bus responses.
No pin multiplexing or electrical pad qualification is implied. Mapped area and timing are reported below through the T21 report link.

## T21 implementation evidence

The opt-in `EmitSocIo` profile binds this peripheral into the full SoC;
`EmitSocI1` retains its original stubs. See the [T21 report](../../../docs/plan/tasks/reports/T21.md)
for current focused simulation, formal and GF180 evidence and exact commands.
Formal scope and assumptions are in [formal/README.md](formal/README.md).
No CI was run. Full-chip clock, pad, hold/RDC and post-placement qualification
is not implied by these block checks.
