# Proposed retained locked-image restart

Status: proposal awaiting the user's reset-policy decision. No RTL change is
authorized by this document. The current recovery-loader reset contract remains
authoritative until that decision is recorded.

## Purpose and boundary

The existing loader retains its programming lock across external reset, lite
watchdog reset and AON service reset, but clears verified-image metadata. The
locked image cannot be uploaded again or explicitly started until cold reset.
The proposed optional profile would retain a descriptor for a previously
CRC-verified, locked image so the existing host START command can restart it.
Older profiles retain their existing behavior. No automatic START, new host
opcode, programming unlock, flash-image ABI or clock-source change is proposed.

This changes the explicit reset policy in
[the loader contract](i2c-recovery-loader.md), which currently requires image
invalidation on external reset/lite watchdog. Generic boot/recovery approval
does not supersede that policy. Independent contract review identified the
conflict before implementation; user approval is required.

## Descriptor and reset semantics

- Capture descriptor validity, validated entry, image length and image identity
  atomically with the first successful existing LOCK or LOCK+START. The existing
  VERIFY and complete-memory-write accounting must have succeeded first.
- Keep the descriptor in the same cold-reset cohort as the programming lock.
  Power-on/brownout asynchronously clears its validity and lock. No retained RAM
  contents by themselves confer validity after cold reset.
- Warm/AON service reset clears started state, partial frames, pending writes,
  CRC work, completion credit and pulses. None of these are restored. The backend
  shares the existing service reset and cancels outstanding writes.
- After qualified service reset release, restore READY, programmed, entry,
  received length and image identity only when both descriptor-valid and locked
  are true. Fence host mutations and START while restoration is in progress.
  Unlocked images remain invalid after reset, even if they had passed VERIFY.
- Restoration never emits START. A later existing host START or LOCK+START
  follows the ordinary admission checks and the real-hart binding. Repeated
  START while running remains rejected. Retained-memory ownership and boot
  release still follow an actually accepted START in the current epoch.
- A cold reset during restoration invalidates the descriptor immediately.
  Repeated warm resets cannot fabricate validity, alter the descriptor or replay
  a previous command. Whole reset still closes performance release; restarted
  lite firmware must release it through the existing boot-control key.

The trust argument is prior successful CRC verification plus immutable program
SRAM while locked. This does **not** recompute CRC after reset or detect retained
RAM bit errors. The programming lock is not an authenticity/security mechanism.
Program writes by every bus/loader writer must be proved impossible while locked;
no new assumption about a writer is permitted.

Estimated descriptor payload at the existing capacity: validity 1 + entry 11 +
length 12 + image ID 32 = 56 bits, excluding any implementation control. This is
a state estimate, not mapped area or a new allowance.

## Verification required before acceptance

1. Existing loader wire/accounting/control tests and negative controls unchanged
   for default profiles; no assertions, caps, bounds or reset assumptions relaxed.
2. Independent host model checks locked/unlocked images, malformed commands,
   wrong CRC, partial upload, repeated lock/start/reset, exact descriptor fields,
   cold invalidation and attempted writes through every production memory ingress.
3. Reset tests around VERIFY, lock commit, START, pending write and restoration,
   including stopped-clock reset pulses and simultaneous reset/command boundaries.
4. Unbounded descriptor safety and production program-write exclusion, with
   covers and actual faults for premature certification, lost cold invalidation,
   incorrect entry and unauthorized program writes. Existing per-job caps apply.
   Any memory abstraction must preserve the audited write-control graph.
5. Actual loader/retained SRAM/lite/boot-control/full-SoC restart, followed by
   performance execution. A locked image starts again only after a new host
   command; main/performance resets preserve the existing AON execution contract.
6. Fresh conservative mapped block timing, complete optional profiles, frozen
   focused regression and independent review. Neither CI tier runs. No physical
   SRAM retention, reset/RDC/hold or production flash-boot qualification follows.
