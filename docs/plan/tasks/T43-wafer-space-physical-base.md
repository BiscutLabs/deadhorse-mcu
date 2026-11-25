# T43 Adopt the wafer.space template and current PDK

## Goal, ordering and scope

D105, user direction 2026-11-24: the physical base is the official
[wafer.space GF180MCU project template](https://github.com/wafer-space/gf180mcu-project-template)
at a pinned commit. Move to that template's PDK_COMMIT. No Coldfoot pad-ring,
slot or flow material may be imported. This supersedes D9's source choice.
T43 is a prerequisite for T38, which retains full physical implementation.

Use its own `codex/` branch rebased onto the then-current production SoC.
Do not mix PLAN05, T41 reset consolidation or T40 DMA implementation into it.
Execution order currently assigned: T41, T40, T42, then this task before T38.
Adding this brief does not change the current PDK or qualify a chip top.

The requested mixed SystemVerilog pad top around the Chisel-emitted core is
a narrow user-authorized exception to D16/D20 and the source-location rule:
template collateral lives under phys/gf180-ws-1x1, with provenance and patches.
The core and peripheral RTL remain Chisel; no general SV exception is granted.

## Read first

AGENTS.md; plans README, STATUS, 01-03, 06-16; T35-T38 and PLAN05 reports;
T41/T40/T42 reports if completed; docs/spec/soc.md, soc-power-reset.md,
soc-physical-boundary.md and USB physical/qualification contracts; soc.yaml;
phys/gf180-ws-1x1; tools/env and tools/physical locks/fetch scripts;
hw/vendor/gf180_sram/gf180_sram.lock.json and preparation scripts;
the upstream template README, LICENSE, Makefile, flake.nix and flake.lock.
Skills: deadhorse-task-execution, gf180-synth-timing-check,
clocked-chisel-block-design, reference-model-testing, chisel-formal-properties,
formal-timeout-triage.

## May change

Physical template/vendor locks and reviewed patches; PDK pins/fetch scripts,
affected environment definitions and timing skill; library-dependent measurement
tools; logical chip top and pad binding; pad boot/reset smoke fixture; physical
constraints/PDN/macro configuration; task records and affected plan/spec sources.
No GPIO-count/function changes, memory-capacity changes, unrelated block RTL,
weaker timing/area limits or replacement of existing functional test assertions.

## Work, in order

### 1. Plan and provenance

Record D105 and T43, make T38 depend on this task, and replace every instruction
to obtain physical material from Coldfoot in docs/plan and docs/spec. Preserve
prohibitions and historical evidence without suggesting imports are authorized.
Search the repository and inspect physical-file history/provenance; the report
must identify the audit boundary and confirm no Coldfoot-derived physical file
exists. Do not copy from the Coldfoot repository to perform this audit.

### 2. Pin only the template collateral used

At execution, query latest upstream main and pin its exact full commit, expected
d99f6e1 or newer. Record the PDK_COMMIT, LibreLane revision and complete Nix
flake.lock dependency revisions/hashes. Retain Apache-2.0 LICENSE/attribution.

Vendor chip_top structure, slot_1x1 and slot defines, 3.3 V SRAM-enabled
LibreLane config/SDC/PDN, padring script and required wafer.space logo, marker,
project-ID, QR and shuttle-ID IP under phys/gf180-ws-1x1. Use a lock containing
source URL, commit and each file's SHA-256, following the SRAM lock style.
Local differences are an independently reviewed patch list, not silent edits.
Stop if a template file needs more than minor adaptation.

### 3. Migrate the PDK without losing the baseline

Preserve reproducible old-PDK inputs/receipts for matched comparisons. Replace
every active 40cee970 pin with the selected template PDK_COMMIT: environment/
fetch scripts, gf180-synth-timing-check skill, plan04_screen.py,
analog/characterization.md, physical pdk-lock and all other hard-coded pins
found by repository search. Historical receipt provenance remains historical,
never relabelled as new-PDK evidence; classify every retained old hash.

Diff 7t5v0 Liberty corners, LEF and cell inventories. Report added, removed and
changed cells, with used-cell coverage. Stop before any repair if a used cell
disappears. Compare new-PDK ocd_ip_sram 1024x8 views with pinned efdbf73 views
by hash. If identical, deduplicate and identify the single source. If different,
keep pinned views, explain differences and ask before switching. Inspect all
other production SRAM views as required by the actual macro inventory.

### 4. Matched area/timing measurements

Relevant checks only, no aggregate fast/full CI (task-specific D76 exception).
Measure old versus new PDK with the same corners, constraints, source snapshot
and accepted timing classes: T35-method chip area/headroom, performance core/
SoC 8 MHz mapping, USB classes, DMA, PWM function and SRAM-interface STA.
PLAN05 implements PWM in the unified timers; measure the production block,
not retired hw/ip/pwm. Report every command/revision and measured wall time.
Cycle counts and functional tests need no rerun unless a library-dependent
netlist check requires them. Stop before fixes if any previously met path fails,
headroom becomes negative or a used cell is missing. Keep hold, electrical,
clock-gate and reset diagnostics and all existing exceptions visible.

### 5. Logical chip top and pad map

Follow the template structure: pad cells and wafer.space IP surround the
Chisel-emitted Deadhorse core. OSC_IN uses dedicated clk and the single active-
low reset uses rst_n. Map every soc.yaml function, including AON_CLK_SEL,
POR_BYPASS, BOOT_MODE, OSC_EN, AON_CLK_IN, USB D+/D-/VBUS/pull-up and JTAG.
Record each pad's index, side, cell type, direction and mux binding. Report
spares against 40 bidirectional, 12 input-only and 2 analog signal pads;
verify these against the pinned slot, not assumptions. Do not change GPIO
count or any pin function. Stop if the simultaneous map does not fit.
Verify the user-specified 1x1 die target of 3932 by 5122 um and 12.92 mm2 core
against the execution-pinned slot; these dimensions are not measured fit.

Compare gf180mcu_fd_io (shared IO/core power) and gf180mcu_ocd_io (separate
domains) for 3.3 V core, 3.3 V IO and USB. Prepare an independently reviewed
recommendation with electrical/power/USB reasons, and obtain user approval
before committing to a pad library.

The user requests twenty 1024x8 SRAM instances in the template's 3.3 V macro
configuration/PDN, replacing its 512x8 example. **Inventory conflict to resolve
before implementation:** completed PLAN05 uses sixteen 1024x8 main macros and
four 512x8 retained macros (2 KiB retained). Do not silently enlarge retained
RAM or misdescribe the production instance types. Present this mismatch for
clarification before configuring SRAM; retain current capacity/views meanwhile.

### 6. Smoke checks, not full physical implementation

Run the unmodified template example through its own flow in the pinned
environment to establish toolchain operation. Then run Deadhorse synthesis,
floorplan, padring and PDN, placing macros only enough to establish pad/core
fit. This global-placement stop applies to Deadhorse only; the unmodified
template baseline runs through its own complete flow. Full Deadhorse P&R
remains T38. Run elaboration and
a short reset/boot test through chip_top pads in the existing simulation flow;
do not add cocotb. No functional silicon, USB electrical or tape-out signoff
follows from these smoke runs.

## Acceptance and publication (unverified)

Before execution, record exact commands supported by the pinned upstream flow
and existing project entrypoints. Acceptance requires authenticated vendor and
PDK locks; complete cell/SRAM comparison; matched measurements without new
failures; approved pad-library choice; complete pad map/spares; original-template
flow pass; Deadhorse pre-global-placement smoke pass; pad-level boot/reset pass;
structure/link/diff checks. No invented CLI or unrun command counts as passing.
Independent review covers provenance/patches, migration/comparison, pad contract,
measurements and final evidence before logical commits/push on this branch.

Write reports/T43.md with Outcome, What changed, Checks run, Numbers,
Deviations from the brief and Open issues. Include commits/hashes, cell/SRAM
diffs, old/new timing/area, pad map/library recommendation, command wall times
and deferred items. Label measured, estimated and assumed quantities. Keep
proof caps unchanged and use one focused timeout triage where relevant; no
unchanged reruns or false proof claims.

## Stop conditions

Ask on pad-map overflow, required pad-library selection, differing SRAM views
before replacement, newly failing timing, negative headroom, missing used cell,
or more than minor template edits. Also resolve the explicit macro-inventory
mismatch without changing memory capacity implicitly. No full P&R, unrelated
RTL work, analog-interface change or acceptance relaxation is authorized.
