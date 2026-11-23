# Pinned PULP debug module

riscv_dbg.lock.json records each upstream repository, commit, imported path and
license. `sha256` is the pinned Git blob (LF). `snapshot_sha256` records the
Windows checkout used for the audit; differences are CRLF normalization only.
`prepare.py` checks pristine and patch hashes, applies the recorded patch under
build/vendor/riscv_dbg and verifies every resulting file hash. Pristine imports
are never modified. The production RTL file list is explicit in the lock.

The integration patch normalizes disjoint reset branches for synthesis, adds a
default-off independent-hart reset-status extension and observation-only command
identity outputs, and extracts the DTM's internal CDC interface. Chisel binds
the extracted TCK handshake through the shared CDC primitives. No upstream
opaque crossing remains in the production file list. No debug authentication
or individual-hart reset capability is advertised.

Standalone DM equivalence does not qualify the replaced transport; scan/CDC
and production OpenOCD tests are separate acceptance obligations. See the
contract and current evidence in hw/ip/debug/README.md and the T32 report.
