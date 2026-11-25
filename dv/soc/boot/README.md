# Production boot peers

`check.py` builds the real ROM and runs the unchanged C policy/recovery code
against independent native binary/CRC/NOR models, then uses actual production
cores and pin-only SPI-NOR/UART peers. No bus master or memory backdoor loads the
images. Passive RVFI/reset outputs check copied bytes, release order, runtime
stack bounds and watcher continuity; this is simulation-only instrumentation.

The finite campaign covers selection, malformed images, held/released lite,
performance-only reset, surviving DMA, update commit order, serial framing,
duplicates and operation-boundary power cuts. Native partial-mutation cuts
supplement the wire checks. A focused IMFC application checks exact arithmetic
and a lite mailbox exchange, not ISA/FP conformance. Watcher-held and maximum
lite-size cases are copy-time fixtures, not watcher execution claims.

Every run preserves source/image/tool commands and artifact hashes. Negative
controls must fail for their intended assertion. The existing scoped policy
allows costly proofs to remain explicitly deferred; no aggregate CI is invoked
here. Required PLAN05 phase-end fast CI is separate.
