# T37 scan/ATPG research and design direction

Research date: 2026-11-26. This is an engineering recommendation, not scan
signoff. The user authorized the original tool proposal if research found no
better approach. Independent review supports that choice for a bounded pilot.

## Conclusion

Retain the pinned OpenROAD flow and add separately pinned Quaigh. Research
did not establish a better drop-in flow for this chip. The useful improvements
are explicit test-access design and faithful fault accounting, not a different
ATPG algorithm or an additional processor-driven test framework.

The implementation contract still needs independent review before production
RTL. The recommendations below implement existing T37/plan08 obligations;
they do not approve new package pins, change functional reset behavior or
waive verification.

## Comparison and source status

| Approach | Evidence inspected | Applicability / decision |
| --- | --- | --- |
| OpenROAD scan + Quaigh ATPG | OpenROAD's pinned DFT documentation and Quaigh source | Keep. Explicit domain/edge chain separation and placement-aware stitching; ATPG uses random patterns followed by SAT for remaining faults. Independent replay remains necessary. |
| PULP Croc | Draft scan PR124, source `45afcc2e037476a5378a58f85571ba84c3d293ab` | Useful small-MCU example: shared UART/JTAG pads, explicit test mode and scan bindings. Still a draft with SRAM observability/control work listed; not proof of a completed production-test flow. No source imported. |
| OpenTitan | Reset-manager RTL and scan-reset verification description | Useful separation of functional and test reset paths. Adopt the control principle, not its security lifecycle or locked-debug policy, which conflicts with D41. No source imported. |
| Fault / Difetto | Fault documentation; Difetto `b1add985a1d40b6269107e4854bb386fb46a9435` | Difetto already uses OpenROAD + Quaigh. Its plugin documents unsupported macros/inouts; its flow lacks distinct test SDC support. Do not replace our physical flow. `nl2bench` is independently available, so Fault need not be installed to obtain a converter. |
| NTU FAN_ATPG | MIT-licensed source `26b2b36c0e9db11a4b6d9e759df6e44357121f39` | Credible alternative with fault simulation, compaction and pattern export. Its custom technology-library path would need a new GF180 adapter and qualification. Research found no demonstrated integration advantage over Quaigh here. Not built. |
| faultflow | Source `c734ee464d69a4b97c1278d4c1f5d81ecef6d813` | Interesting explicit fault accounting and transition support. Documented PDKs are Sky130/OSU035; upstream discloses historical scan over-credit in some benchmark rows. Those results are not GF180 qualification. Not selected or built. |
| Commercial ScanPro/FastScan or TestMAX | Vendor descriptions | Mature facilities for clock-domain partitioning, scan compression and broader fault models. A useful methodology reference, but no licensed installation is available in this project. No unsupported claim that open tools replace their signoff coverage. |

Sources:

- [Pinned OpenROAD DFT documentation](https://github.com/The-OpenROAD-Project/OpenROAD/blob/dcf36133a369abc8f3c5e5738cd4d82e4903c0e0/src/dft/README.md).
- [Croc draft PR124](https://github.com/pulp-platform/croc/pull/124) and
  [its scan binding](https://github.com/pulp-platform/croc/blob/45afcc2e037476a5378a58f85571ba84c3d293ab/openroad/src/dft_config.tcl).
- [OpenTitan reset-manager implementation](https://github.com/lowRISC/opentitan/blob/master/hw/top_earlgrey/ip_autogen/rstmgr/rtl/rstmgr.sv).
- [Difetto](https://github.com/donn/difetto),
  [Fault](https://fault.readthedocs.io/en/latest/usage.html),
  [standalone nl2bench](https://github.com/donn/nl2bench).
- [FAN_ATPG](https://github.com/NTU-LaDS-II/FAN_ATPG),
  [faultflow](https://github.com/ranaumarnadeem/faultflow).
- [Siemens ScanPro](https://www.siemens.com/en-us/products/ic/tessent/test/scanpro/),
  [Siemens MemoryBIST](https://static.sw.cdn.siemens.com/siemens-disw-assets/public/81225/en-US/Siemens-SW-Embedded-memory-self-test-repair-and-debug-Tessent-MemoryBIST-FS-81225-C1),
  [Synopsys TestMAX DFT](https://www.synopsys.com/implementation-and-signoff/test-automation/testmax-dft.html).

## Design direction for Deadhorse

These are project-specific inferences from the sources and our current netlist.

1. **Separate test mode from scan shift enable.** Test mode owns pads, safe
   output clamps, test clock/reset selection and SRAM isolation throughout
   shifting and capture. Dropping scan enable for capture must not restore
   functional outputs or normal clock/reset ownership. Use an explicit,
   clocked entry sequence; exit through reset before functional execution.
   Exact entry encoding/shared-pin mapping remains to be specified/reviewed.
2. **External test access must work without CPU or DMI service.** Existing
   JTAG debug is not a manufacturing scan path. Avoid requiring a functioning
   core, bus or scanned debug logic to shift its own tests. Reuse shared pads
   as plan08 requires; do not add a second general debug processor or TAP.
   Account explicitly for the small unscanned test-control state and test it
   separately, rather than hiding it in a denominator.
3. **Partition chains by actual clock and edge.** Start with OpenROAD
   `no_mix`, not clock mixing plus new lockup storage. Derived/gated clocks
   need explicit treatment; there are more clock nets than named domains.
   Force the shared gates through their test-enable pins with a controlled
   external clock. Keep functional clocks unchanged. Do not infer that slow
   shifting fixes hold or reset-removal issues. The pinned `scan_opt` is a
   no-op, so rely on the verified stitching behavior, not newer documentation.
4. **Keep SRAM March separate from logic scan.** Disable macro writes and
   isolate unknown macro outputs during logic tests; preserve T35 BIST port
   ownership. Any added macro interface observation/control must be measured
   and tested. A blackbox output is not an independently controllable input
   unless hardware supplies that control. Analog tests remain separate.
5. **Model only real scan observations.** Quaigh's automatic `expose_dff`
   exposes nonconstant enable/reset as outputs as well as D. Those are not
   necessarily observable on the chip. Construct the combinational cut from
   controllable scan Q and observable capture D/package signals under the
   actual protocol, and prove correspondence. Do not create arbitrary cut
   points at block or clock-domain boundaries. Preserve cross-domain faults.
6. **Use explicit physical fault-site accounting.** Quaigh's default
   `redundant_faults` removes structurally equivalent faults; that is distinct
   from SAT-proven untestability. Report physical gate-pin sites separately
   from expanded BENCH primitive sites, and independently replay detections.
   Unknown, aborted and excluded faults remain visible. No coverage floor is
   invented; unsupported transition coverage stays open.
7. **Start without scan compression or logic BIST.** Our inference is that
   uncompressed scan and the existing memory BIST offer the simplest first
   implementation. Measure chain lengths, runtime and toggle activity before
   adding compression hardware. Quaigh stores a pattern-by-fault matrix and
   constructs fault/good SAT networks; a tiny successful run is not evidence
   that a full-chip job fits the minimal-test budget.

Quaigh source references:
[ATPG/cutting](https://github.com/Coloquinte/quaigh/blob/5b47ca63608d516efc3f225758635df689be70c5/src/atpg.rs),
[fault representation](https://github.com/Coloquinte/quaigh/blob/5b47ca63608d516efc3f225758635df689be70c5/src/sim/fault.rs).

## Area feasibility screen

Measured inventory command at `d496b9c539729cef58180ba605c41a5201f68cb6`:
`python scratch/t37_scan_inventory.py`; receipt
`build/t37/research01/inventory.json`. It reads the existing T43 production
mapping (SHA-256 `aaa6bb843bb316b2577a5e0e7bea032063f908ef25db1696bc7ab335c415b368`)
and the pinned TT 3.3 V Liberty, not a new synthesis run.

| Measured existing FF type | Count | Library area, um2 | Candidate scan area, um2 |
| --- | ---: | ---: | ---: |
| dffq_1 | 7,145 | 63.6608 | 83.4176 |
| dffrnq_1 | 12,919 | 74.6368 | 94.3936 |
| dffsnq_1 | 314 | 79.0272 | 98.7840 |
| dffnrnq_1 | 2 | 74.6368 | No same-family scan counterpart |

Estimated ordinary replacement delta:
`(7145 + 12919 + 314) * 19.7568 / 1e6 = 0.4026040704 mm2`.
This excludes the negative-edge solution, test control, muxes, buffering,
clock/reset distribution, timing repair and routing. It is not mapped scan area
or a headroom acceptance result. The two negative-edge cells must be handled
explicitly, not silently excluded or changed to positive-edge behavior.

## Scoped pilot result

`tools/physical/atpg.lock.json` pins Quaigh and its source/build-lock hashes.
The tool builds in its own locked environment; the physical flow pins are
unchanged. No Fault, FAN or Difetto package was installed.

Measured `tools/physical/atpg_pilot.py` result in `build/t37/pilot02/result.json`:
four patterns, eight exhaustive input assignments, and all twenty enumerated
gate-input/output stuck-at sites detected for a four-cell cone feeding
`_218088_/D`. Separate Yosys/Liberty replay agrees with the reference truth
table and detects actual output-stuck faults; an empty pattern set is rejected.
Measured checker wall time: 0.831541 s. Exact command and binary/input hashes
are in the receipt and T37 report.

The initial random patterns detected all sites before compaction, so this
pilot did not exercise SAT fallback. Independent review authenticated the
source tree, tool/input/output hashes and all replay rows. The reusable runner
still needs enforced approved input/tool hashes and classified failure/timeout
receipts before production qualification; this pilot was authenticated manually.

This qualifies a small combinational generator interface only. The cone's
independent cut inputs are not a proof that all those assignments can yet be
loaded on the production chip. No scan-cell insertion, physical scan shifting,
clock/reset protocol, macro isolation, whole-chip fault coverage or full
functional equivalence has been qualified. No aggregate CI ran.
