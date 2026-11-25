# 09 Roadmap

PLAN03 consolidates existing digital IP and prepares the remaining briefs under
D72-D76. Planning does not start a new implementation task or close a stage.
Shuttle target is wafer.space GF180MCU 1x1; date and staffing remain open.

## P0 Foundation

1. PLAN01 reconciles decisions, plan, affected specs and task briefs.
2. T08 establishes pinned Linux Docker/WSL environment; T01 scaffold/CI follows.
3. T02 reproduces historical workload; T06 reproduces RISCay clocked baseline.
4. T07 establishes direct Chisel build and formal smoke; T05 builds register
   tooling using format fixtures, not an unresolved actuator ABI.
5. T09 establishes per-block GF180 timing. T10 pins the Ibex reference and
   builds the comparison harness; T11 converts it to Chisel with equivalence
   proved; T12 builds the FPU in parallel; T13 integrates F and improvements
   so S1 can measure the result. No alternative-core evaluation.
6. T14 specifies and builds the whole-chip bus fabric, domain bridge and
   mailbox, and specifies the gateway protocol (D43). T03, T04 and S2 are
   withdrawn with the NoC.
7. Prepare separate briefs for RISCay adoption, analog layout/characterization,
   shared CDC, peripherals and physical import. These are not implemented by
   the documentation update. Obtain USB implementer sizing and delivery evidence.

**G0:** decisions recorded; USB boundary and sizing/delivery assumptions explicit;
scaffold and CI working. An approved boundary is not a delivered USB block.

## P1 Design qualification

S1 measures the selected Chisel core/FPU; T14 reports bus, bridge and mailbox area and proofs;
S3 validates capacity/XIP/banking; S4 measures latency and test coverage.
Prototype harnesses are Chisel, output under build/. Measurements do not replace
independent correctness checks. T10-T13 are implementation, distinct from S1 measurement.

**G1, architecture freeze:** satisfy formal smoke and shared-CDC proof requirements;
validate loop target/fallback and full F; measure area/timing; qualify memory and
test approach; freeze clock/CDC/reset partition, simultaneous pin map, ownership
rules, and physical/USB reservation. Verify shuttle/library/SRAM/process options.
No unresolved assumption affecting area, pads or clock domains may be presented
as frozen. Approval of a capacity or part does not establish fit.

Existing S1 target: at least 5 MIPS; between 2.5 and 5 MIPS requires documented
500 Hz fallback and actual loop validation. Below 2.5, stop for review. No
automatic core substitution, FPU removal or relaxed acceptance limits.

## P2 SoC and FPGA

The SoC follows stages I0–I5 of [16-soc-integration.md](16-soc-integration.md).
PLAN03 leaves one production DeadhorseSoc with all built digital blocks; old
profiles are historical test evidence. ADC hardware is retired, and the I2C
loader is frozen. No new opt-in feature configurations.

D88/D89 place [T39 focused core/SoC regression](tasks/T39-core-soc-qualification.md)
before physical acceptance, using the implemented cores and T32–T34 integration
with their recorded exceptions. Run existing standalone core, lite, production
clock/reset, flight/wake, debug and complete fast-tier checks. New ISA/ISS
frameworks, broad seeded coverage and full state observers remain deferred;
this finite pass does not establish complete architectural qualification.
T35 SRAM/BIST and T36 production ROM follow, then T37 test/scan and T38 chip
top/pads/LibreLane. Replay affected T39 checks after memory, boot and scan
changes; T38 requires current scoped evidence with its limitations, not just an earlier pass.
T34 analog interfaces/models do not supply physical layouts; layout/extraction
needs a later brief. No unbriefed peripheral work.
Existing T20 composition/system and inherited proof debt remain visible in STATUS.
D76 requires fast CI before new block work and after every task; full CI at
each I2/I3/I4/I5 exit. Neither approval nor a fast pass completes a stage.

Implement independent models for selected sensors/actuators, timer-driven flight
firmware and system/FPGA tests. Specify generic PWM buffered-update and DMA contracts before their ABI freeze;
application command-timeout/recovery and publication remain firmware concerns
under D69. Include scan, SRAM self-test and analog
test controls. Do not import neural IP or add a chip-to-chip link.

**G2:** simulated flight through hover/transition/forward flight, real actuator
timing tests, retained sleep and UART modes, DMA/ownership, JTAG wake/debug,
reset containment, boot/recovery and clock-selection tests. Clean structural
CDC, per-block GF180 timing, formal ledger and core correctness evidence;
no Coldfoot FPGA interoperability gate. No silicon performance claim from FPGA.

Historical D18 Click option is separately deferred; it has no dependency in
this initial clocked implementation and may only start under an explicit brief.

## P3 Physical

T43 first pins and qualifies the official wafer.space template/PDK under D105.
T38 uses that accepted base to floorplan SRAM, analog, pads
and optional USB. Include clock trees/gates, scan, CDC/reset and full timing at
qualified corners with extraction. Analog DRC/LVS/antenna and startup/corner
campaigns, supply monitor safe defaults/selection and extracted sleep power.

**USB cutoff is before Phase 3 floorplan freeze.** Integrate and verify by then
or omit and use UART/JTAG. The reservation is not permission to integrate after
freeze without reopening affected checks.

**G3:** all physical signoff gates in [08-physical-verification.md](08-physical-verification.md),
including equivalence. No blanket approval of assumed area or coverage.

## P4 Silicon

Tapeout after qualification, bring-up board with external clock/reset access,
flash and baseline peripherals, test/calibration, characterization and staged
flight validation. No required die-link header or LF crystal. Final timeout,
recovery, timing and electrical policies must be validated before free flight.

**G4:** product definition of done. A subsequent chip-to-chip/neuromorphic
project requires its own scope, source rights and plan.
