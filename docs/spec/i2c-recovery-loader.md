# Lite I2C recovery loader

T18 contract at the pinned RISCay revision
`4671317186003740ceb61360ba08c59bbdf10136`. The programming lock follows Deadhorse plan 12.
The external programmer owns SCL. The lite subsystem receives commands and
can pull SDA low. The endpoint operates before lite firmware is available.

## Transfer and snapshot

The seven-bit default address is 0x35 (write byte 0x6a, read byte 0x6b).
Transfer bits MSB first and encode each 32-bit parameter least-significant
byte first. A write contains one opcode and its exact payload. The target
accepts at most 33 data bytes including the opcode. STOP or repeated START
publishes a selected nonempty write. Malformed length, overflow or a trailing
partial byte rejects the command. Preserve the pinned target's exception for
the single preparatory SCL rise used to form a STOP or repeated START. A byte
ACK acknowledges wire receipt. The host checks loader status for the result.

At read-address acceptance capture the entire selected bank and its support
mask. Send eight consecutive little-endian data words, then one little-endian
32-bit word whose low eight bits mark supported entries. Missing entries read
as 0xffffffff with the corresponding bit clear. Widen address increments so
that word 255 cannot wrap. The programmer can NACK early and must NACK its
last byte. Status reads preserve the error and the selected address.

| Opcode | Bytes including opcode | Effect and owning service |
| --- | ---: | --- |
| 0 | 4 | SELECT takes three bytes in order (space, instance, starting word). It updates the selector and preserves the previous error. |
| 1 | 33 | BEGIN takes eight words in order (image bytes, entry offset, expected CRC32, ABI version, required working RAM, required GPIO mask, required channel count, image ID). Validate before invalidating a previous image. |
| 2 | 9 | WRITE takes the next byte offset and a word. Issue one program-memory write with all lanes enabled. |
| 3 | 1 | VERIFY requires a complete image and matching CRC. Publish valid and READY on success. |
| 4 | 1 | LOCK a verified image. Repeating LOCK on a running verified image is allowed. |
| 5 | 1 | START a verified image at its recorded entry. Reject a second start while running. |
| 6 | 1 | LOCK and START together under the same start checks. |
| 7 | 5 | Housekeeping sample-period request. With sampling unavailable, the pinned implementation reports range error 4. |
| 8 | 1 | Deliver the host wake event to AON. |
| 9 | 1 | ENTER_LOADER belongs to boot/recovery policy. With the flash-boot backend absent, report incompatible (5). |
| 10 | 1 | PERSIST belongs to boot storage. With the flash-boot backend absent, report incompatible (5). |

Modes are BOOT=0, LOADING=1, READY=2, RUNNING=3 and FAULT=4. Error values
are success=0, malformed=1, locked=2, busy/reset context=3, range=4,
incompatible=5, invalid state=6, incomplete=7 and CRC mismatch=8. The flash
service reserves error 9 for persistence failure. Preserve command-specific
priority from ClockedControl. In particular, reject malformed
frames before dispatch, allow SELECT while a write is pending, and reject
mutations on a frame whose captured application-reset context is active.

Device space 0, instance 0 reports ABI 0x00010000, application ID/version,
program/working RAM sizes, GPIO/channel counts, reset reason and crash count
(words 0–8). Loader space 1, instance 0 reports mode, programmed, locked,
can-program, busy, last error, image ID, received bytes and boot state
(words 0–8). With no flash backend the boot state has no active session,
pending persistence or hold. Spaces 2, 3 and 128 belong to measurement,
timing and application services. Expose only supported resources and advertise
actual capabilities consistently with BEGIN checks. Boot ROM, QSPI and gateway
integration have separate owners.

## Program memory and admission

Check length and entry as full unsigned 32-bit byte values before narrowing.
Length is positive, aligned to four and within capacity. Entry is aligned and
strictly below length. Require the supported ABI, sufficient RAM and channels,
and a subset of available GPIOs. Reject out-of-order WRITE offsets. Begin
the reflected CRC32 at 0xffffffff, process the four bytes of each word in
increasing address order and complement once for the VERIFY comparison.

A single accepted WRITE owns its byte offset and word through memory
completion. The backend may stall. Publish the incremented received count and
updated CRC once the four lanes have committed. A completion with no matching
outstanding write has no effect. After reset, the backend and endpoint must
flush stale responses before accepting new work. Frame dispatch has priority
over the Stored accounting event in the reference fabric, so a concurrent
response must remain available until accepted. The admission and CRC pipeline
must preserve the first observable next-transaction result.

`memValid` offers one aligned word at `memOffset` (byte offset relative to lite
program SRAM) with all four byte lanes enabled. Both offset and `memWord` stay
stable until the rising edge with `memReady`. The backend returns a one-edge
`memDone` after acceptance and flushes uncommitted traffic on whole-domain
reset. The controller captures a completion concurrent with a frame and
publishes it on the next free edge. CRC32 is prepared iteratively before
offering the write. The received count and CRC become architectural together.

The standalone profile advertises application ID/version 1/1, configurable
program and working RAM (defaults 2048/1024 bytes), zero GPIOs and zero
measurement channels. The synchronous `resetReason` and `crashCount` device
inputs come from AON. `halted` is the CPU's held halted level. `entry` is
the validated byte offset and `start` is a one-edge admission pulse. The
CPU uses that offset only at an admitted start. `wake` pulses for opcode 8
and `clockHold` requests continued service while the target or write is busy.
The address-only wake probe is captured by the external AON wake controller.

## Clock, wake and reset

D83 exception for first-silicon POR_BYPASS mode: external pin reset is cold
and clears the programming lock along with other cold-only chip state. Normal
mode retains the warm-pin lock policy below; watchdog containment is unchanged.
The loader RTL is unchanged; the production reset controller selects the cohort.

The pinned ClockedFabric samples the wire on an ungated front clock and asserts
that the phase-related work clock is running at frame or read-bank capture.
Use one qualified active service clock for the adopted endpoint, with the
shared synchronizer on each asynchronous pin. The reference requires at least
eight service edges per SCL period and never stretches SCL. Its default idle
limit is 262144 service edges with no observed transition during an active
transfer. On timeout release SDA and discard the partial transaction. The
integration must keep the service clock running until active work drains.
PLAN04/D82 binds this service directly to nominal 32 kHz AON with no fast
service mode. The host must limit SCL to the minimum qualified AON frequency
divided by eight. Estimated nominal ceiling: 32000 / 8 = 4000 Hz. If the
assumed -5% RC limit is qualified, the corresponding estimated ceiling is
3800 Hz; until characterization this is not a guaranteed limit. The fallback
external AON clock obeys the same ratio. No loader RTL, assertion, timeout or
clock-stretching behavior changes. Recovery remains accessible while OSC_EN
is low, because this target never depends on OSC_IN.

The following stopped-HF probe description is historical upstream context,
not a requirement to stop or restart the production loader's AON clock:
For a stopped HF source the programmer sends START, the write address 0x35
and STOP with no opcode or data. Either ACK or NACK is valid on that probe,
which must leave the image and lock untouched. The programmer waits the
published wake interval and starts a fresh transaction within the published
hold window. RISCay assumes a 100 µs wait after STOP and a subsequent 50 µs
start window. Deadhorse integration must establish those intervals against
actual clock startup and retention. The AON wake path must be available
before HF starts.

| Event | Endpoint behavior |
| --- | --- |
| Host reboot, bus recovery or retained sleep | Preserve committed image metadata and programming lock. Discard interrupted traffic according to framing and timeout rules. |
| Performance-domain reset | Preserve the AON loader, lock and lite state per D37. |
| Power-on reset or brownout | Release SDA, clear valid, started, pending and lock, and return to BOOT. RAM can contain committed bytes. A fresh upload must verify before start. |
| External reset or lite watchdog | Release SDA, invalidate the image, discard pending work and return to BOOT. Retain the programming lock. When locked, reject fresh BEGIN and WRITE until POR/brownout. |

The reset controller supplies two qualified active-low signals. A POR or
brownout asserts both por_n and reset_n low. External reset and lite watchdog
assert reset_n alone. The whole-domain reset_n controls all ordinary state.
Only por_n controls the lock flop. The
memory backend must share the warm-reset flush boundary. The endpoint has no
performance-domain reset input. This approved policy preserves the plan 12
lock invariant and D37 reset containment.

Sources: pinned ClockedI2cTarget, ClockedFabric, ClockedControl, ControlSchema,
Platform, HostSchema, SocSpec and upstream docs/loader-status-and-lock.md.
Deadhorse requirements are in the [reset plan](../plan/06-power-clock-reset.md)
and [formal plan](../plan/12-formal-verification.md).
