# USB vendor reference

Pristine MIT `ulixxe/usb_cdc` sources at the commit in `usb.lock.json`.
`patches/sie.patch` records the supplied snapshot's completed-IN ACK
qualification fix. `prepare.py` verifies every hash and applies that patch
only to `build/vendor/usb/`. The original import is never modified.

`patches/sie-zlp-retry.patch` is the D54 scoped bulk retry repair: a distinct
pending bit retains an actually offered terminal ZLP until qualified ACK,
separately from eligibility after a full packet. Directional clear-halt clears
both states. EP0 response selection is unchanged. The lock records the patch
and final applied hashes; protocol, formal and timing qualification is required.

Production retains SIE and PHY RX/TX behind a Chisel BlackBox. Other modules
are conversion references, not production endpoint implementations. See
[USB contract](../../ip/usb/README.md) for conversions and accepted PHY
structural exceptions. All protocol/timing verification remains required.
