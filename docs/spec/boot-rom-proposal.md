# T36 boot-path feasibility and proposed contract

Proposal for approval, not the implemented SoC contract. Inspected at main
`27307fcad45985582cd0b28400933abdfb8b11ba`. D91 authorizes scoped verification;
it does not resolve the mapping/ownership decisions required by T36.

## What exists

| Boundary | Current production behavior | Consequence |
| --- | --- | --- |
| Lite reset/start | `SocI1Peripherals` supplies START only from a validated, idle loader, with an aligned entry below 2048 bytes | No autonomous boot |
| ROM | `soc.yaml` maps 0x00000000–0x0000ffff main-local; `SocLocalMemory` admits performance and authorized debug | Lite cannot fetch trusted ROM |
| Retained program | `SocRetainedMemory` rejects ordinary writes to the first 2048 bytes; remaining 1024 bytes are working RAM | Lite firmware cannot load its own image |
| Performance release | `BootRelease.bootSeen` means a validated loader START was observed | ROM startup cannot currently authorize release |
| Recovery ownership | Loader program writes require the actual lite hart halted and loader unlocked | WFI is not a recovery handoff; the running hart must really relinquish its client |
| UART/QSPI | UARTs belong to performance; QSPI resets to lite, with idle-only owner handoff | UART recovery belongs in performance ROM; flash access must be handed over |
| Gateway | v1 specifies a distinct gateway-origin master; firmware emits its core origin | Firmware cannot claim general gateway-master permissions |

Source owners: `hw/top/reference/src/main/scala/deadhorse/top/` for the
assembly and memory boundaries, `hw/ip/boot_control/`, `hw/ip/lite_core/`,
and [gateway v1](gateway-protocol.md). No RTL has changed for this proposal.

## Recommended boot binding

1. Give each core a synchronous, immutable local ROM view in the existing
   0x00000000–0x0000ffff aperture. Lite's view resides in AON and needs no
   main-clock progress to fetch. Performance keeps its existing reset entry
   at 0x80; lite starts its own ROM at zero after qualified reset. This adds
   a local ROM binding, not shared access to performance SRAM or a new address
   window. Actual ROM contents and mapped area must be measured; the aperture
   is not permission for an arbitrary ROM capacity increase.
2. Add a small top-level boot sequencer with explicit ROM, sealed application
   and loader-wait modes. Debug halt-on-reset takes priority and cannot lose
   the pending ROM start. It must not manufacture loader validity or START.
3. During trusted lite ROM boot only, allow checked writes to the existing
   2048-byte program region. Close this permission irreversibly for the whole-
   reset epoch before application entry. Ordinary application writes remain
   denied. A later jump back into ROM cannot reopen it. CRC, bounds and entry
   validation remain firmware obligations, tested at actual instruction entry;
   a boot-phase bit is not a hardware CRC proof or an authentication claim.
4. This ROM-copy authority is separate from the frozen loader's lock: a whole
   reset may revalidate and refill from flash even when that loader lock is
   retained. It never clears the lock or enables host programming. This is
   an explicit new trusted write authority requiring approval, not an implicit
   exception to the current program-write assertion.
5. Feed qualified trusted-ROM startup, as well as real validated loader START,
   into the existing performance-release sequencing. Preserve its key and
   existing offsets. In ordinary boot, lite validates configuration and its
   image before releasing trusted performance ROM, which validates/copies its
   own image before application entry. Lite stays in ROM until both cores have
   agreed that the same selected bundle is valid and completed a current-epoch
   readiness/commit handshake; neither application starts on partial success.
   Lite never writes performance SRAM.
6. In the no-valid-image case, permit trusted performance ROM to run for UART
   recovery even though no lite application was validated. Both applications
   remain unentered. This is a specific recovery exception to ordinary boot
   order, not permission to execute an unchecked image.

Whole-chip reset restarts the sequence from immutable ROM. A reset confined
to a client or AON service must not reopen a sealed program-write permission,
reuse stale handoffs or overwrite memory owned by a surviving application.
If that reset prevents safe continuation, fail closed and require a whole-
chip reset; do not invent a retained-image restart of the frozen loader.
Performance-only reset returns to trusted performance ROM without resetting
shared peripherals, DMA or the lite core (D70). Before reloading performance
SRAM or reentering the application, it must obtain explicit ownership/drain
confirmation and a same-generation handshake with the surviving lite application.
Acquire QSPI through its existing idle handoff, never by forcing shared-service
reset. It must not select another paired generation or overwrite a live DMA
buffer. If this cannot be established, fail closed pending a whole-chip reset;
autonomous restart is not promised.

## Recovery and update boundary

Use UART0 in performance ROM with its existing owner and register interface.
Preserve v1 COBS, CRC, sequence/duplicate handling and framing, but advertise a
distinct firmware-recovery capability profile. It uses native core permissions;
it does not impersonate gateway/debug origin. Only explicitly reserved recovery
staging RAM is writable by LOAD/WRITE32; live ROM stack and control data are
excluded. Unsupported accesses and reset operations are rejected. JTAG remains
the full physical debug/programming path. Exact capability and recovery-command
encodings must be specified and independently reviewed before firmware tests.

Transfer lite payload/configuration through the existing checked mailbox to
lite ROM while it still owns its boot phase; performance copies its own data.
Use the existing QSPI idle handoff for flash programming. Updates run in trusted
recovery firmware, with applications not running. Stream bounded chunks into
the inactive flash slot, then validate the complete stored bundle before commit;
do not require a full image plus recovery stack to fit in RAM at once. No generic
hardware UART gateway or recovery-loader extension is added.

The I2C fallback must be real: finish outstanding ROM/bridge/mailbox work,
close ROM-copy permission, acknowledge the handoff command, then reset/drain
the lite client and leave it actually not started. Disable automatic ROM start
in loader-wait mode. Only the existing loader's validated START can then launch
the uploaded lite image. Do not spoof `halted`, reuse JTAG ownership as boot
authority or mix transport payloads. Inhibit loader mutations through its
existing integration interlock while ROM owns the program memory; preserve
status and existing busy/error semantics. Locked warm-reset recovery remains
locked and requires the existing cold-reset procedure for host programming.
The UART service must relinquish shared flash/mailbox resources before the
loader-started image takes over.

## Paired-image policy to approve

Adopt the pinned RISCay CRC/compatibility, A/B/golden and commit-last approach,
adapting the record to a **paired lite/performance/configuration bundle**:

- A factory-owned, CRC-protected directory describes disjoint aligned A, B
  and golden regions within the declared flash capacity. Bad directory means
  serial recovery, not guessing a golden address.
- A bundle binds architecture/ABI, generation, configuration, each image's
  source/destination lengths, entry points and CRCs. Reject wrap, overlap,
  unsupported versions and SRAM/stack violations before copying or entry.
  Each executable segment, including any declared cold XIP segment, must have
  explicit bounds and integrity coverage. There is no signed authentication.
  Configuration is bounded, versioned data for existing supported controls and
  the application; unsupported trim/control settings are rejected, not an
  authorization to add T34 analog calibration hardware.
- Select the newest fully usable field bundle; A wins equal generations.
  Try the other field bundle, then golden, then recovery. Never combine cores
  or configuration from different generations. Performance validates its own
  selected record before application entry; any late failure keeps both
  applications from entering until the current-epoch commit. After either
  application has entered, a later fault is runtime recovery, not a retroactive
  boot-validation guarantee; whole-chip reset is required before changing bundles.
- Update only the inactive field slot after validating the previous usable
  bundle. Keep directory, golden and the previous usable field slot intact.
  Verify body and header readback, then program and verify the commit magic
  last. Reject generation exhaustion instead of wrapping. Interrupted update
  must leave the previous complete bundle bootable. No watchdog-based health
  scoring or automatic rollback of a CRC-valid application is introduced.
- Initially support the pinned baseline's ordinary NOR command family:
  mode-0 READ/RDSR/WREN/PAGE PROGRAM/sector erase, 24-bit addresses, 256-byte
  pages and 4 KiB sectors. These are proposed compatibility requirements,
  not a qualified board part. Firmware polling is bounded; actual part,
  erase/program bounds and pad timing remain qualification obligations.

The pinned source is RISCay `4671317186003740ceb61360ba08c59bbdf10136`,
`tools/boot_image.py`, `tools/boot_slots.py`, `firmware/boot/boot.c` and their
contracts. Its existing format is single-image and its ROM uses loader MMIO
absent from Deadhorse. Do not copy that loader interface, its retained restart
policy or unrelated/asynchronous RTL. Preserve licensing/provenance for code
actually adopted. The two-core binary ABI must be versioned, not presented as
compatible with the old format or the unchanged I2C BEGIN record.

## Acceptance after approval

Keep T36's original boot/update/serial-wire, malformed-image, power-loss,
two-hart debug and affected T39 checks. Add ownership/seal/reset and loader-
handoff properties with negative controls; scoped timeouts stay unproved under
D91. Compare image parsing against an independent oracle. Measure both ROMs,
working-RAM/stack, boot/recovery time, flight cycles, mapped timing and the
whole area budget. Stop for fit/limit failures rather than raising capacities.
No CI, unrelated IP tests, full gateway compliance, physical signoff or stage
exit is claimed by this proposal.
