# Retained raw ADC acquisition (T27)

D71 (user approval2026-11-21) retires scaled_sample at0x14. Every other offset
is preserved. Software must read raw_sample and convert/calibrate in firmware;
no raw alias or zero-success response remains at the retired address.

Adopt the serial receive engine `ClockedSpiAdc` from
pinned RISCay 4671317186003740ceb61360ba08c59bbdf10136. Preserve its mode-0
16-clock frame, 12-bit sample extraction, first-conversion discard after
reset. D69/D71 move conversion and calibration to firmware. The wrapper registers the
result and pad outputs, adds shared MISO synchronization, MMIO, owner checks
and sticky events. Provenance records source hashes and each adaptation.

The peripheral lives in AON, within the existing ADC window at 0x40020000.
Its generated register window occupies only the low256bytes; other addresses
error. Trusted owner is lite origin0. It has one CS and no MOSI/ready input;
no claim of simultaneous voltage/current acquisition or external-part/pad
qualification follows. Production selects rawOnly=true; legacy arithmetic
parameters do not affect production raw codes. The scaler remains only as
a historical reference/verification fixture.

`halfPeriodCycles` is an elaboration parameter, minimum4 (default5) to allow
the shared synchronizer and registered pad boundary. This minimum must pass
the independent wire test; it is not inherited qualification. An active frame
has32 half-periods, followed by a registered completion cycle. SCLK is low and CS high
when idle; output enables are off after reset and while disabled.

APPLY atomically installs enabled/continuous/idle-gap settings only when neither
frame/completion nor a launch is pending. Rejected APPLY sets config_error and
leaves active settings unchanged. START is accepted only enabled, idle and
manual; otherwise command_error. Continuous mode automatically launches when
idle-gap countdown reaches zero. The gap counts idle service edges between
operations, as in the pinned source; it is not a fixed sample-period guarantee.
The gap must exceed40*halfPeriodCycles. Disabling drains by requiring idle
before APPLY; service reset may abort immediately. First-frame discard resets
only on service reset, not on configuration changes. Valid sample updates
raw/sequence together. Overrun is sticky if an unread sample is replaced;
READ_ACK clears unread, with new data winning simultaneous acknowledgement.
APPLY+START rejects both with config_error and no launch or configuration change.
READ_ACK concurrent with a sample acknowledges the previous result: unread
remains set for the new result, but that replacement is not an overrun. Software
reads sequence, raw, then sequence again and retries if changed; one
register transaction does not snapshot the other registers. Complete that read
sequence before the 32-bit sequence counter can wrap through a full modulus.

| Offset | Register | Fields |
| --- | --- | --- |
| 0x00 | configuration | rw enable0, continuous1, reset0 |
| 0x04 | idle_gap | rw32, reset100000 |
| 0x08 | command | w1p APPLY0, START1, READ_ACK2 |
| 0x0c | status | ro busy0, enabled1, continuous2, primed3, unread4 |
| 0x10 | raw_sample | ro bits11:0 |
| 0x14 | retired/reserved | all reads/writes error, including zero-strobe writes |
| 0x18 | sample_count | ro32 sequence |
| 0x1c | events | w1c sample0, overrun1, config_error2, command_error3 |
| 0x20 | irq_enable | rw bits3:0, reset0 |

IRQ and clockHold are registered. ClockHold stays asserted through launch,
frame and completion, and throughout enabled continuous operation. Its service
clock must remain running accordingly. Reset flushes ordinary state and
outputs; no retained sample across service reset is promised. Source clock
rates, serial rate and throughput must be labelled measured/estimated in the
report. Mapped area/timing are recorded in the T21 report; physical ADC compatibility remains unqualified.

## Integration and evidence

The opt-in `EmitSocIo` profile binds this peripheral into the full SoC;
`EmitSocI1` retains its original stubs. See the [T21 report](../../../docs/plan/tasks/reports/T21.md)
for historical scaled-ABI evidence. The [T27 report](../../../docs/plan/tasks/reports/T27.md)
records the raw migration and its current focused commands/results.
Formal scope and assumptions are in [formal/README.md](formal/README.md).
No CI was run. Full-chip clock, pad, hold/RDC and post-placement qualification
is not implied by these block checks.

## Raw completion and publication

Production uses the raw engine in manual-start mode, with continuous
scheduling implemented by the existing wrapper. On the final internal
falling SCLK edge, the engine captures its12-bit result and sets registered
done. Busy includes that completion cycle. The wrapper then publishes the
registered result while its registered CS returns high; it never publishes
the engine's changing shift register. First completion after service reset
only primes the receiver. Removing the arithmetic tail changes completion
latency and continuous cadence; no legacy cycle-equivalence claim is made.

AdcSampleState holds the registered raw result, sequence and unread state.
Without a sample, raw/sequence hold; READ_ACK clears unread. A new sample
increments the sequence once and wins over simultaneous READ_ACK, leaving
unread set. Simultaneous READ_ACK retires the previous sample, suppressing
its overrun. The local combinational overrun pulse feeds the generated sticky
event register on that same publication edge; it is not an external block
boundary. Hardware event set wins over simultaneous software W1C.
Service reset clears all publication and sticky event state and aborts the
wire frame. All crossings still use the shared MISO synchronizer.

`sw/hal/adc_convert.h` performs explicit rational gain/offset conversion,
floor division and unsigned32-bit wrap. Invalid code, zero denominator or
null output pointer is rejected without changing output. It embeds no board
calibration. The former25300/4095 ratio is an example caller configuration.

The raw engine has seven unbounded manual-start assertions at halfPeriod4;
publication-state proof assumptions are initial reset low, then arbitrary
sample/data/ack/reset. Denied-owner and legacy arithmetic checks stay
separate; see [formal/README.md](formal/README.md). Physical ADC part, pad,
clock/hold/RDC and full-chip qualification remain open.
