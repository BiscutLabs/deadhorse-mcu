# Gateway protocol v1

T14 specification only. The gateway RTL and host client belong to a later brief.
UART and optional USB CDC-ACM carry the same byte stream; JTAG is independent.
No signed firmware or authentication is introduced. Physical access permits
debug/programming subject to the same bus ownership/memory checks.

## Frame

Use COBS encoding, followed by a zero delimiter. The decoded frame is:

| Bytes | Field |
| --- | --- |
| 0 | Version, 1 |
| 1 | Opcode; response sets bit 7 |
| 2–3 | Little-endian sequence number |
| 4–7 | Little-endian byte address or reset selector |
| 8–9 | Little-endian payload length, 0 through 256 |
| 10 onward | Payload |
| Last 4 | Little-endian CRC-32/ISO-HDLC over all previous decoded bytes |

CRC parameters: polynomial 0x04c11db7, reflected input/output, initial value
0xffffffff, final XOR 0xffffffff; check value for ASCII `123456789` is
0xcbf43926. CRC detects corruption; it provides no authentication. Limits are
protocol constants, not measured throughput. Invalid COBS, CRC, length or
truncated frames have no side effects and are discarded until the delimiter.
An otherwise valid frame with unknown version/opcode/reserved fields receives
BAD_REQUEST. No command executes until the entire frame is validated.

## Requests and replies

One request is outstanding per transport session; the host waits for its reply.
The gateway returns exactly one reply for each valid request accepted by a live
session. Replies echo version, opcode|0x80 and sequence; payload begins with a
status byte: OK=0, BAD_REQUEST=1, DENIED=2, BUS_ERROR=3, TIMEOUT=4, BUSY=5.
Reply bytes 4–7 echo the request address/reset selector. LOAD replies always
include the two-byte completed-byte count after status, including failure replies;
validation failure or BUSY reports zero completed bytes.
All reserved bits/fields must be zero. Extra requests during execution receive
BUSY with no side effect and are not executed later.

| Opcode | Request | Success reply after status |
| --- | --- | --- |
| 0x01 READ32 | Aligned address, empty payload | Four little-endian data bytes |
| 0x02 WRITE32 | Aligned address; four data bytes and one byte-enable byte (low four bits) | Empty |
| 0x03 LOAD | Aligned RAM address; nonempty payload, multiple of four bytes, at most 256 | Two-byte completed-byte count |
| 0x04 RESET | Address selector 0=performance reset, 1=whole-MCU reset; payload little-endian key 0x44524853 | Empty acknowledgement before requesting reset |
| 0x05 INFO | Zero address, empty payload | Protocol version, implementation ID and capability bitmap, defined by gateway brief |

LOAD is a sequence of checked full-word writes to permitted RAM, not flash
programming and not an atomic transaction. Reject address wrap, invalid length
and disallowed region before issuing any beat. Recheck ownership at each beat;
on error stop and report completed bytes. A failed beat may have an uncertain
outcome if its response was lost; completed-byte count excludes that beat.
RESET acknowledges before reset assertion; the session then ends and the host
must reconnect/resynchronize. Loss of power/reset may prevent any reply.

Requests use the bus contract's gateway origin and endpoint checks. Access to a
mailbox staging interface requires exclusive ownership or a halted core; a host
cannot interleave a staged message with live core software. DMA and private
memory restrictions are not bypassed. USB availability changes only transport,
not permissions or command semantics.

## Recovery

Keep the last completed request bytes and reply within the live session. An
identical immediate duplicate with the same sequence replays that reply without
re-executing; the same sequence with different bytes is BAD_REQUEST. A duplicate
while the original runs is BUSY. No replay guarantee survives reset or power
loss. The host must not automatically retry side-effecting commands after an
ambiguous timeout. A readback or explicit recovery sequence determines state.

Frame-receive idle timeout and physical UART rate are configuration values for
the gateway brief. Timeout discards partial input without execution. A valid
bus request follows the bus completion watchdog; TIMEOUT is distinct from a
positive cancellation acknowledgement. The byte transport and reply buffering
must provide bounded service under an explicitly stated host-read assumption.
Malformed-input, duplicate, reset and stalled-host tests are mandatory when
implemented; this document claims no gateway verification result.
