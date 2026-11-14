# T09 Per-block GF180 timing flow

## Goal

Implement the check specified in [../14-timing-design-rules.md](../14-timing-design-rules.md).
Required before S1; FPGA timing is not a substitute.

## Read first

- [../../../AGENTS.md](../../../AGENTS.md)
- [../08-physical-verification.md](../08-physical-verification.md)
- [../14-timing-design-rules.md](../14-timing-design-rules.md)
- T06 report and T08 environment locks

## Inputs / May change

Requires T01, T06, T07 and T08. May change `tools/timing/`, CI integration,
timing constraints under `phys/gf180-ws-1x1/`, timing ledger and report. No core
changes, library substitution, waived violations or timing-budget relaxation.

## Steps and deliverables

Create `tools/timing/check.py` to synthesize a named emitted block with pinned
tools to gf180mcu_fd_sc_mcu7t5v0, run open static timing at the specified corners,
enforce the existing per-block budget and record critical paths/cell area and
assumptions. Test a known failing path and a passing example. Keep routed
signoff distinct from this pre-layout check. Verify SRAM and clock constraints
are not silently omitted; identify unsupported macro views as blockers.

## Acceptance checks

Proposed interface, **not run by PLAN01**:

```sh
python3 tools/timing/check.py --self-test --output build/t09
python3 tools/ci.py
```

Self-test must show a real failing path is rejected and a valid path passes;
record exact synthesis/timer invocations and negative-control evidence. Confirm
RISCay's documented slow path with its T06 exported design where reproducible;
do not manufacture a measurement or weaken a ceiling to match old results.

## Stop and ask

Required library/corner/tool unavailable, constraints unsupported, or a check
cannot distinguish the positive/negative controls. Report rather than waive.
