# Production boot contract — PLAN05

Approved architectural replacement under D92–D101 (user 2026-11-24).
Implementation and acceptance remain unverified. This replaces the former
lite-first proposal, not historical evidence. Phase1 contracts require
independent review before RTL; exact firmware recovery encodings require review
before tests. See [PLAN05](../plan/tasks/PLAN05-dormant-coprocessor.md).

## One boot master

There is one immutable ROM in main, in the existing 0x00000000 aperture, reset
entry 0x80. Performance boots first. Lite has no ROM and remains reset until
performance releases it to its program-RAM base. No boot sequencer modes,
ROM-copy seal epochs or cross-core readiness/commit handshake are needed.
Measure ROM content bytes and mapped area against plan08's existing allowance;
the aperture is not an authorization to grow that allowance.

Whole-chip sequence: POR/brownout and external pin released; AON source running
and count-qualified; AON released with lite held reset; external oscillator
stable; main released; performance ROM executes:

1. Read reset-sampled BOOT_MODE: normal selection or UART recovery wait.
2. Read and validate the factory directory. Select newest fully valid A/B
   paired bundle, otherwise golden, otherwise recovery. A wins ties; reject
   generation exhaustion rather than wrap. No mixed-generation images.
3. Copy and verify performance image into main SRAM.
4. Copy and verify lite image into retained program RAM while lite is held
   reset. Apply the bundle's lite-start flag: release now or leave held for
   the application. All bundle records/images are validated before release.
5. Enter performance application, whose startup initializes data and bss.

BOOT_MODE is a reset-sampled alternate function of GPIO1/AON MOSI, with board
pull-down for normal boot or pull-up for recovery. Keep outputs disabled while
sampling, freeze the selection before enabling serial outputs; radio CS has a
board pull-up. Performance-only reset uses the retained boot context rather
than resampling or reselecting a bundle.

## Lite memory authority

Only performance-origin transactions may write lite program RAM, and only while
boot control holds lite in reset. ROM and applications use the same hold/write/
release procedure. Halt/drain the lite client before acknowledging the writable
hold; debug ownership cannot masquerade as boot hold. Release starts at program
base. Other program writes return errors without modifying memory. Lite cannot
write its own code. Direct debug SBA program writes are denied too; unlocked
JTAG can use performance-hart execution to load it under boot hold. Preserve
positive SBA tests in data memory and explicitly test program-write rejection.
This is integrity, not security; D34/D41 remain.

Retained RAM stays powered. Size and program/data split follow the measured
watcher under D96, not an arbitrary default. Resetting performance does not
reset lite, reopen a program-write window, or alter its RAM. Whole-chip reset
holds lite again. Existing lite-watchdog whole-chip behavior remains; if a
lite-only reset scope is later enabled, it must hold lite and notify performance
via mailbox for explicit reload/release, as C5 requires.

## Performance-only reset

D70 preserves DMA and shared services. Enter a stackless ROM preamble and wait
for existing DMA and QSPI activity to drain before any SRAM writes or stack use.
Use a bounded wait; on timeout remain fail-closed in ROM until whole-chip reset.
Do not abort/reset DMA, reconstruct its buffers, negotiate with lite or force a
shared-service reset. Test a permanently stalled DMA channel as well as normal
drain. This admission guard prevents a surviving bus master racing ROM's stack,
CRC/reload or application initialization.

A retained validated context identifies the originally selected generation and
slot/record. Verify the same-generation performance image CRC in SRAM. If it
matches, skip flash copy; otherwise validate and reload that same image from
flash. Never reselect a newer bundle or touch lite memory/reset. Application
startup always initializes data/bss. If a valid same-generation image cannot
be established, fail closed in ROM until whole-chip reset. Exact context fields,
CRC coverage of immutable image versus runtime data, reserved stack/context
bounds and finite wait counts must be reviewed before implementation; no
unreviewed ABI or numeric timeout is implied here.

## Bundle and flash policy

Retain the pinned RISCay CRC/compatibility, A/B/golden and commit-last approach,
adapted to a versioned paired performance/lite/configuration bundle:

- CRC-protected factory directory defines disjoint aligned A/B/golden regions
  inside declared flash capacity. Invalid directory enters recovery; do not
  guess a golden address.
- Versioned ABI includes generation, image source/destination lengths, entries,
  CRCs, configuration and lite-start flag. Validate alignment, bounds, overlaps,
  program/data/stack allocations and compatibility before execution. Explicitly
  bound and cover any cold XIP segment. CRC is not signed authentication.
- Select newest fully valid A/B, A on ties, then golden, then recovery.
  Validate the complete paired bundle before releasing lite. After application
  entry, changing generations requires whole-chip boot, not live negotiation.
- Stream bounded chunks to inactive field slot, preserving directory, golden
  and previous usable slot. Verify body/header readback, program/verify commit
  magic last. Power loss must preserve the previous complete bootable bundle.
- QSPI belongs to performance from reset. Ordinary mode0 NOR baseline remains
  READ/RDSR/WREN/PAGE PROGRAM/sector erase, 24-bit addresses, 256-byte pages and
  4 KiB sectors. These are compatibility assumptions, not a qualified board
  part. Bound polling against independently reviewed part assumptions.

Reference provenance: RISCay commit
`4671317186003740ceb61360ba08c59bbdf10136`, `tools/boot_image.py`,
`tools/boot_slots.py`, `firmware/boot/boot.c`. Preserve licensing for adopted
code. Its single-image ABI/loader MMIO is not the new paired ABI and must not
be copied into the production interface.

## Recovery and sleep

UART0 performance-ROM recovery retains gateway v1 COBS/CRC/sequence/duplicate
framing with an explicitly advertised firmware capability subset. Use native
core permissions, never gateway/debug impersonation. LOAD/WRITE32 may access
only reserved staging RAM, excluding live stack/context. Unsupported addresses,
operations and reset commands error. Exact command/capability encodings require
independent review before serial-wire tests. Enter on BOOT_MODE or absence of a
valid bundle. JTAG is full fallback. No I2C loader, loader-wait/handoff or
runtime ownership transfer remains.

Sleep and dormant wake resume the retained performance core after WFI, never
ROM. A valid watcher packet requests wake through mailbox; raw radio GPIO and
AON SPI IRQs wake lite only. The performance watchdog is frozen for committed
dormant through oscillator startup qualification; lite watchdog remains active.

## Required evidence

Keep T36 original boot/update/power-loss/malformed-image/serial-wire obligations
and affected two-hart debug/core checks. Add lite release, program-write denial,
performance-only reset/same-generation and failed-DMA-drain cases. Account for
every retired loader/seal/handoff test under the explicit PLAN05 removals.
Independent review covers this contract, exact encodings and implementation.
Run fast CI at Phase2 and Phase3 ends; D91 scoped tests apply only to iterations.
No phase acceptance, ROM fit, physical qualification or gate closure is claimed.

PLAN05 BOOT_MODE readback: performance reads bit0 of boot-control offset0x10
(`0x40000310`), read-only. GPIO1/AON MOSI is sampled on AON edges while
whole-chip reset qualification is pending and frozen before AON clients release.
Main-only or AON service reset does not resample it; a new whole-chip reset does.
A board strap must remain stable through whole-chip reset qualification.

## T36 concrete ABI (independently reviewed; acceptance pending)

This section fixes independently reviewed implementation choices for Phase3;
it is not a completed implementation or a new memory-capacity decision.
All integers are unsigned little-endian. CRC uses gateway CRC-32/ISO-HDLC.

### Directory and paired record

Retain the pinned eight-word factory directory: magic0x32425352, version2,
sector-aligned slot stride, sector-aligned declared flash bytes (at most16MiB),
A address=4096+stride, B=4096+2*stride, golden=4096, CRC over the first28bytes.
Require positive stride and4096+3*stride <= declared capacity using subtraction
bounds before arithmetic. Directory and golden are never field-erased.

A paired header is96bytes at slot base, followed by erased padding through
byte255 and contiguous performance, lite and configuration payloads from256.
No arbitrary segment offsets or XIP entry is accepted in ABI3; all executable
bytes are copied to the two existing RAM apertures. Later cold-XIP formats
require a separately reviewed ABI, never an unchecked entry in this format.

| Word | Meaning / validation |
| --- | --- |
| 0 | Paired magic0x33424844 |
| 1 | Format3 |
| 2 | Generation: golden0; A/B1 through0xfffffffe; no wrap |
| 3 | Flags: bit0 releases lite after copy; all other bits zero |
| 4 | Performance image bytes: nonzero, multiple4, <=14336 |
| 5 | Performance entry offset: halfword aligned, inside image |
| 6 | Performance image CRC |
| 7 | Lite program bytes: nonzero, multiple4, <=1024 |
| 8 | Lite entry offset: zero, matching boot-control fixed base |
| 9 | Lite program CRC |
| 10 | Configuration bytes: multiple4, <=256; zero permitted |
| 11 | Configuration CRC (zero for empty payload) |
| 12 | Performance total image/runtime/data/bss/stack allocation: >=image bytes, <=14336 |
| 13 | Lite runtime data/bss bytes |
| 14 | Lite stack bytes: >=16; data+stack <=1024 with subtraction bounds |
| 15 | Required performance MISA: RV32 plus subset of implemented IMFC |
| 16 | Required lite MISA: RV32E, exactly0x40000010 |
| 17 | Hardware ABI1 |
| 18 | Extent: exactly256+performance+lite+configuration, <=slot stride |
| 19-21 | Reserved zero |
| 22 | CRC over first88header bytes |
| 23 | Commit0x54494d43, programmed only after complete verification |

Validate every header, destination, CRC and paired payload before selection.
Validate complete A/B candidates; choose higher generation, A on equality;
otherwise validate golden. Bad directory enters recovery without a guessed
flash destination. Required performance MISA must include RV32I and contain no
unsupported bits; the actual hart supplies IMFC. Header allocation claims are
compatibility bounds, not a proof of arbitrary application memory safety.

Performance starts at0x20000000+entry. Its CRC-covered image remains immutable
in place; application startup copies initialized data from that image into its
separate runtime allocation and clears bss on every entry. Lite startup likewise
initializes data in0x30000400-0x300007ff from constants in program RAM. Program
and data never overlap. Configuration is copied to the reserved readout below;
application entry registers a0/a1 give its address/length, a2 gives generation.

### ROM working memory and reset classification

Reserve0x20003800-0x20003fff (2048bytes) in the firmware ABI, without changing
hardware SRAM size or access permissions: configuration256bytes at0x20003800,
context128bytes at0x20003900, staging256bytes at0x20003980, firmware globals
through0x20003dff, stack512bytes at0x20003e00-0x20003fff. Linker assertions and
measured stack/high-water must fit; no allocation growth is implied.

A hardware read-only boot-status bit3 records a fresh performance-watchdog
reset since the current whole-chip boot epoch. It clears with boot-control
whole/AON reset; a stale watchdog reset-hold spanning that reset does not set
it (observe hold low before a later rising edge). Whole reset dominates. This
is reset metadata, not a program-write seal; C3 permissions are unchanged.
It distinguishes reset during context preparation too: a set bit requires
current-epoch committed context or fail-closed, never reselects. A clear bit
follows the cold path. Read-only status bit4 is `contextReady`, cleared by
whole/AON reset and preserved across performance-only reset. The performance
owner sets it by writing key0x434f4e54 to boot-control offset0x14 only after
the context is complete; other origins or keys error without effect. This
metadata prevents surviving RAM from a previous whole-chip epoch being accepted
if the performance watchdog interrupts cold context preparation. It neither
grants access nor changes C3's write rule. Reset dominates a simultaneous key.

The128byte context uses words0-4 for magic/version/stride/flash-capacity/slot,
words5-28 for the complete96byte header, word29 for CRC of words1-28, and
words30-31 zero. It is committed with magic last after copies verify
and before the hardware context-ready key, lite release/application entry.
Performance-only reset requires hardware context-ready, then validates
context structure/CRC/bounds and revalidates the same slot/header/generation in
flash. Matching immutable SRAM CRC skips copying; otherwise reload exactly that
performance image. Never write lite/configuration or reselect A/B. Missing,
changed or corrupt context/header/image fails closed until whole-chip reset.

A stackless reset preamble waits for DMA busy=0 and QSPI busy=0 before any SRAM
write. Assumed drain timeout2s at nominal8MHz, enforced with unsigned cycle
elapsed plus a finite poll bound; no timeout extension, DMA abort or recovery.
After drain, initialize only ROM globals/stack, preserving committed context.
A fresh performance reset before context commit therefore fails closed safely.

### Firmware UART capability and update commands

UART0 uses8N1, assumed115200baud at8MHz (integer fractional increment selected
and measured by the build); no USB recovery transport. Keep gateway-v1 framing,
CRC, sequence/duplicate handling, status meanings and256byte payload cap.
Partial receive idle timeout assumed100ms at8MHz. Noise/overflow/timeout drains
to delimiter, with no command effects. An identical immediate duplicate replays
the reply; same sequence/different bytes is BAD_REQUEST. Reset ends the session.

INFO after status returns one protocol-version byte1, four-byte implementation
ID0x35304844, four-byte capability bitmap0x00000117 (READ32/WRITE32/LOAD/INFO,
plus bit8 paired update). READ32/WRITE32/LOAD are restricted to staging only.
WRITE32 preserves byte-enable semantics; LOAD replies with completed count even
on failure. RESET and all unknown commands are BAD_REQUEST/no effect. No native
MMIO, application, stack, context, configuration or lite memory is exposed.

| Opcode | Request | Result |
| --- | --- | --- |
| 0x10 BEGIN | Address0=A or1=B, payload96byte uncommitted header (commit=0xffffffff) | Validate header/geometry, newest-generation rule and inactive slot; erase only that slot; retain candidate header in ROM working RAM |
| 0x11 DATA | Address is next expected slot-relative offset, payload nonempty/multiple4<=256 | Stream from offset256 to declared extent, strict sequence; word writes do not cross256byte pages; verify readback before acknowledgment |
| 0x12 COMMIT | Address0, empty payload | Require complete extent, verify all payload CRCs, program/verify header words0-22, program/verify commit word23 last |

Update generation must exceed every currently valid field-slot generation;
reject exhaustion. The newest valid field slot is never erased; if no field
slot is valid, either field slot is eligible while golden remains untouched.
No update is possible without a valid factory directory. A failed operation
invalidates the update session and requires a new BEGIN; duplicate replay must
not erase/program twice. COMMIT returns to UART recovery; application entry
requires a whole-chip reset, which also loads the paired lite image.

NOR assumptions: mode0 single-bit READ03, RDSR05, WREN06, PP02 and sector
ERASE20;24bit addresses,256byte pages,4096byte sectors. QSPI half-period4main
cycles gives estimated1MHz SCK at8MHz. WIP polls are bounded by assumed2s per
erase/program and finite iteration count, matching the prior proposal's
conservative operation budget; timeout is reported, never treated as success.
Physical flash selection/characterization remains separate.
