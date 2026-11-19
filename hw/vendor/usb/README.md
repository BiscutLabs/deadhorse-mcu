# USB vendor reference

Pristine MIT `ulixxe/usb_cdc` sources at the commit in `usb.lock.json`.
`patches/sie.patch` records the supplied snapshot's completed-IN ACK
qualification fix. `prepare.py` verifies every hash and applies that patch
only to `build/vendor/usb/`. The original import is never modified.

Production retains SIE and PHY RX/TX behind a Chisel BlackBox. Other modules
are conversion references, not production endpoint implementations. See
[USB contract](../../ip/usb/README.md) for conversions and accepted PHY
structural exceptions. All protocol/timing verification remains required.
