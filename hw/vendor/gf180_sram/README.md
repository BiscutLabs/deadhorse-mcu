# Pinned GF180 SRAM views

The lock selects the Apache-2.0 GF180 1024x8 byte-write macro. `prepare.py`
extracts exact Git blobs at the pinned revision, authenticates every file and
materializes views under `build/vendor/gf180_sram/`. No vendor HDL or generated
view is edited or committed here. Host checkout line-ending settings do not
affect hashes.

The digital contract, metadata inconsistencies and qualification limits are
documented in [the SRAM block](../../ip/sram/README.md) and
[physical handoff](../../../phys/gf180-ws-1x1/sram.md). License verification and
functional simulation are not physical qualification.
