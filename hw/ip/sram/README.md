# Production SRAM and destructive self-test

T35 production macro wrappers and destructive self-test; results and remaining
qualification limits are recorded in the task report and formal README.
The user-authorized D90 scope runs relevant memory/integration checks only,
without aggregate CI, and records proofs that exceed the existing timeout budget.

## Macro binding

The selected macro is `gf180mcu_ocd_ip_sram__sram1024x8m8wm1`, Apache-2.0,
at revision `efdbf734d806c2ac3b858d281a5b832625a8e928` of
[the pinned upstream](https://github.com/RTimothyEdwards/gf180mcu_ocd_ip_sram/tree/efdbf734d806c2ac3b858d281a5b832625a8e928).
`hw/vendor/gf180_sram/gf180_sram.lock.json` pins each view and specification file;
`prepare.py` verifies and materializes them under `build/vendor/gf180_sram`.
Vendor files are never edited.

Each word bank has four byte-wide macros. The performance memory has four
interleaved banks: word bits [1:0] select the bank, [11:2] select its row,
and each byte enable selects its corresponding little-endian byte lane.
The retained bank exposes rows 0 through 767 only. Its remaining physical
rows are inaccessible to functional traffic and BIST. Logical capacities and
permissions remain 16 KiB and 3 KiB; no ROM or USB-buffer replacement is included.

Inputs are sampled on the rising edge. CEN, GWEN and individual WEN bits are
active low. CEN is high throughout cold reset and before the first operation.
Read data is available after that edge. Writes have no architecturally visible
read data; the existing bus controllers return zero for writes. A disabled
macro or a write holds Q. No reset initializes memory. Simulation and proofs
must allow arbitrary initial contents and compare data only after initialization
by the test or firmware.

Use the explicit A[9:0] ports and LEF dimensions, not stale Liberty metadata
(`address_width=9`, area inconsistent with LEF). The vendor Verilog is a
functional reference only: it initializes RAM to zero and its `specify` delay
contains a documented guess. Neither is a production guarantee. Timing must use
all five pinned 3.3 V-family Liberty corners (SS at 3.0 V, TT at 3.3 V, FF at
3.6 V, including both supplied temperature extremes). Keep the inconsistent
vendor truth-table labels and metadata visible in the physical handoff.

CEN-high sleep retains contents at the normal operating supply, with no SRAM
power gating. This is not a low-voltage data-retention or brownout-retention
claim. Physical characterization, macro-view reconciliation and rail margins
remain physical signoff obligations; digital simulation does not close them.
The pinned vendor datasheet specifies operation from 1.62 to 3.63 V and
-40 to 125 degrees C, with CEN-high standby holding state. These are upstream
specifications, not measurements performed here. T35 timing uses only the
3.0/3.3/3.6 V characterized family; it makes no 1.62 V timing claim.

## Exclusive test ownership

Contract accepted by independent review before RTL:

1. The debugger explicitly asserts `dmcontrol.ndmreset` first. BIST start is
   accepted only with DM active and whole-system reset acknowledged in both
   main and AON. This is destructive manufacturing/bring-up test, not a
   non-destructive operation on halted software. Both cores, DMA, loader,
   fabrics and functional memory controllers are held in reset; accepted
   functional transactions are cancelled by the existing whole-reset contract.
2. A full-word keyed start on the custom DMI device acquires a POR-owned test
   reset hold. It remains asserted until both memory test agents have completed
   and acknowledged relinquishing their physical ports. Clearing `ndmreset`,
   deactivating DM, resetting the TAP, or issuing resume/SBA commands cannot
   release this hold or grant functional RAM access.
3. The memories have one physical port each per bank. A local test mux admits
   either the BIST request or a live functional controller, never both. A BIST
   operation additionally requires the functional service reset to be asserted.
   Functional chip enables are disabled during reset. The test agents use
   POR-qualified clocks/resets and survive warm reset.
4. Main/AON requests and acknowledgments cross only through shared CDC levels;
   multi-bit result records cross through the shared FIFO. The AON request is
   held until its completion record has returned. Release waits for the AON
   agent to observe request removal. A stopped AON clock therefore keeps the
   system safely reset; it cannot produce a false pass.
5. The BIST epoch is `coldReset_n && warmReset_n` (the external pin reset),
   excluding `ndmreset` and the manager's own reset hold. Use this same epoch
   on both agents and every BIST CDC endpoint. Cold/pin reset aborts BIST and
   clears its status; memory contents after an
   interrupted test are unspecified. There is no warm-reset abort or implicit
   retry. DMI transport reset flushes a pending response, not a destructive test
   already accepted. Test status is held in registers outside tested SRAM.
6. On completion, the debugger must reload both memories before resuming code
   that relies on their contents. The loader's cold-owned lock remains set if
   previously locked: use permitted debug writes, or cold reset to reopen the
   loader. Image-valid/boot-release state clears through whole warm reset.
   The reset release primitives still qualify
   each domain's release. BIST does not bypass the oscillator stability policy.

The custom device occupies unused DMI words 0x70–0x7f, not the system MMIO map.
The RISC-V 0.13.2 [DMI contract](https://github.com/riscv/riscv-debug-spec/blob/d5029366d59e8563c08b6b9435f82573b603e48e/debug_module.tex)
allows additional custom debug devices in the DMI space. Ordinary DM addresses
remain forwarded unchanged; this is not a claim that 0.13.2 defines these CSRs.
The register description is the source of the custom CSR decode and tooling.

## Test algorithm and fault scope

March C- over every accessible word, all four byte lanes together:
`up(w0); up(r0,w1); up(r1,w0); down(r0,w1); down(r1,w0); up(r0)`.
Each read is compared only after the synchronous read edge. Record the first
failing logical word address, expected/observed data and phase, then finish
without reporting pass. Successful completion must account for every operation.
An all-zero/all-one background exercises each bit; it does not qualify all
physical coupling, retention or analog faults. The campaign must separately
inject stuck-at, transition and address-alias faults, plus wrapper lane and
early-completion negative controls, and report only demonstrated coverage.
