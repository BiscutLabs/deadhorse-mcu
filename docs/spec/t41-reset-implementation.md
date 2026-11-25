# T41 remaining reset and warm-boot implementation contract

Status: independently reviewed implementation contract within approved
D103/D106/D107. Wiring and warm ROM are implemented on the task branch;
final acceptance remains tracked in STATUS and the T41 report.

## Reset ownership

One raw cold source follows the static POR_BYPASS selection. One raw warm source
combines cold, the normal-mode pin, both watchdog holds and debug ndmreset.
There is no existing software-reset command to add here. The already documented
BIST test hold remains a request to hold warm-controlled consumers, while its
owner survives ndmreset and its own test hold. D107 preserves selective pin abort.
USB keeps its existing incoming source predicate and internal reset handling;
the performance watchdog must not acquire an unapproved USB-reset effect.

Each reached domain owns one cold and one warm ResetRelease where required;
consumers receive those qualified releases without local cascades. Cold owns
reset causes, watchdog history/hold, debug and clock/bootstrap controllers.
Warm owns cores, ordinary peripherals and their application transports. Clock
qualification is state: warm release waits for the required qualified clock,
but controller/debug clocks must remain able to run while ndmreset holds warm.
Do not reset the controller that is responsible for restarting its own clock.

The oscillator controller clears its policy/source epochs on a captured warm
entry, then restarts and qualifies while warm may remain held. Deep sleep must
clear source-local qualification and stale commands before OSC_EN falls,
acknowledging the clear while the source is still running. Reopening requires
fresh qualification. Retained sleep does not assert warm or cold reset.

Lite boot HOLD is a local acknowledged initialization operation. After draining
accepted work it initializes every resettable lite register, including its
register file, CSR, pipeline and debug state. Only the completed initialization
acknowledgement grants C3 writes to program RAM. It must not be replaced by
merely stopping the core clock. RAM contents themselves survive cold and warm.

D106/D107 cancellation fences remain explicit exceptions. Their admission
acknowledgement does not replace accepted-work ownership or BIST quiescence.
Event-capture state for pin/POR/GPIO is inventoried separately from reset trees.

Preserve the existing strap epochs: POR_BYPASS stays static while powered.
AON_CLK_SEL may resample only under cold or external-pin reset, as it does now;
watchdog, BIST and ndmreset must not switch the AON source. Selection remains
held until that selected clock has run through the existing qualification.
Share the retained external-pin event capture with cause/abort handling rather
than constructing another consumer reset tree. BOOT_MODE may resample while
application warm reset is held, but warm ROM ignores it; only cold-path ROM
uses it to choose recovery. A changed strap cannot turn warm restart into
flash reselection or recovery.

## Warm-boot metadata and cause ABI

Keep the existing retained context location and format: ABI constants
`0x20003900`, 128 bytes, version 1 (defined in `sw/boot/boot.h`), selected slot, directory bounds and the
complete paired-bundle header, with the existing CRC coverage and commit-last
magic. No new selection policy, directory rescan or generation negotiation is
introduced on warm restart. A cold-owned hardware context-ready bit records
that ROM committed this context during the current power epoch. Warm preserves
it; cold clears it. SRAM retention alone never establishes context validity.

The existing boot-status bit 3 becomes `fresh_warm_reset`, replacing its narrower
performance-only meaning. It starts clear at cold boot, captures any subsequent
warm entry and stays set until cold. Boot-status bit 4 remains `context_ready`.
Warm entry capture must not miss a pin pulse that occurs with AON stopped.
Cold initialization is not itself reported as a subsequent warm reset.
Arm warm-history capture only after the initial warm release has been observed
in AON. The shared release's first stage is sampled by the same-clock history
flop on the exact edge that updates its final release stage. This extra fanout
is only for history, never a consumer reset or a qualified CDC output; include
that path in the CDC/RDC and timing inventory. Cold release precedes warm
qualification. Thereafter observing the shared AON warm release low records the warm
entry; its asynchronous assertion retains a complete pin pulse with AON stopped.
The raw source causes are captured independently of aggregate warm transitions:
an external-pin pulse while ndmreset already holds warm still records pin cause
and performs D107's BIST abort. Multiple sources may coalesce into one warm
episode without losing their cause bits. Context-ready does not arm capture:
a later warm reset during context preparation must fail closed, not reselect.

Warm ROM requires committed context, validates its format/CRC/bounds, and
revalidates the same slot/header/generation in flash. Invalid or unavailable
metadata fails closed in ROM; it does not select a different bundle or enter
UART recovery. BOOT_MODE still selects recovery on the cold path.
Consequently a normal-mode pin reset cannot clear invalid retained context or
force UART recovery: it is warm. Recovery from this fail-closed condition needs
a genuine cold reset/power cycle, or unlocked D41 JTAG. In POR_BYPASS mode the
external pin is the selected cold source, as before.

With lite held, ROM CRC-checks both immutable performance and lite image extents
against that selected header. If both match, it skips both image copies. If
either differs, it reloads and verifies both images from the same bundle.
Configuration keeps its existing retained bytes on warm restart. The application
must not treat them as revalidated: neither the context CRC nor the image CRCs
check the retained configuration bytes. The application
always initializes data/bss; runtime-mutated bytes within an image extent simply
make its CRC fail and require reload. The lite-start flag is applied only after
both images are confirmed. Dormant wake remains resume-after-WFI, not this path.

Application entry retains `a0=config address`, `a1=config length`, and
`a2=generation`. Add `a3=reset information`:

| Bit | Meaning |
| --- | --- |
| 0 | Existing POR cause |
| 1 | Existing brownout cause |
| 2 | Existing external-pin cause |
| 3 | Existing performance-watchdog cause |
| 4 | Existing lite-watchdog cause |
| 5 | Debug ndmreset observed |
| 6 | This ROM entry followed cold initialization, rather than warm reset |
| 7–31 | Reserved zero; no software-reset source currently exists |

Bits 0–5 are held history since cold, matching the existing cause-register
semantics, not an invented single winning cause. Extend the read-only
power-reset cause field from bits 4:0 to 5:0 without moving its register or
altering prior bits. Debug history survives warm and clears only on cold.
No analog threshold interface changes are part of this amendment.

Required replacement tests cover CRC-valid/no-copy, each image corrupted,
invalid retained context, wrong generation, held-lite write protection, cause
handoff, every warm source and debug survival. A corrupt-image skip-reload
negative must fail. Existing cold selection/recovery and malformed-image
assertions remain. The accepted D104 maximum-image load-latency exception is
retained; T42 owns any transfer optimization.
