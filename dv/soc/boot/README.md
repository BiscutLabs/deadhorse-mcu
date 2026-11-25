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

## T42 load qualification and passive profiling

`python dv/soc/boot/load_profile.py --output build/t42/final-load02` runs only
the production watcher-held and maximum-lite-held boot cases with the original
wire/image checks, always requiring the original250ms budget without D104.
It does not replace `check.py` or the full wire campaign.
Optional `DH_TRANSFER_TRACE` writes passive CSV observations; it changes no
stimulus or acceptance threshold. Pre-edge handshakes and instruction-qualified
post-edge RVFI identify every copy/readback word. Run
`python dv/soc/boot/analyze_load.py --profile build/t42/final-load02 --output build/t42/final-analysis02`
for authenticated stage attribution and corrupted-trace negative controls.
Outputs must be new directories under `build/`; execute through the pinned
environment. Source labels assume the held-lite, single-outstanding load cases,
not concurrent-master attribution. Unused post-response grant requests are
distinguished from accepted transfers; every accepted effect is accounted for,
including between CPU transactions. Twelve corrupted-trace controls test this
observer; the bridge tests separately inject actual transport faults.

`wire_campaign.py --t42` selects relevant malformed-image, warm-boot, retained
memory, DMA-drain and reset-during-copy/readback cases, plus the actual warm-skip
ROM fault. Its receipt lists every unrun case. This scoped mode does not replace
the default full campaign. See the T42 report for commands, measured counts,
estimated nominal-clock latency and retained proof/physical limitations.
