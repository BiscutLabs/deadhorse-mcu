# USB sampling follow-up — 2026-11-22

The production engine's eleven temporal sampling assertions are proved
unbounded. Timing-exception acceptance and the complete USB aggregate remain
open. No production RTL, assertion, traffic assumption or timing limit changed.
This is the user-approved T19 closure prerequisite for PLAN03 B3.

## Proof and witness scope

`UsbSampling.scala` is an observation-only reference bound to the complete
production engine, including SIE/PHY. Configuration: VID/PID zero, 16-byte bulk
packets. Only initial root reset is constrained; subsequent reset, VBUS, pad
and application inputs are arbitrary. No traffic assumptions, initialized RAM
or cutpoints are introduced. Actual SIE use guards output comparisons; the
direct descriptor reference bypasses all three production ROM/select stages.

| Job | Assertions | Result | Measured time |
| --- | ---: | --- | ---: |
| lookahead03 | 4: cursor, remaining, terminal ZLP, completion | ABC PDR PASS, unbounded | 2.374 s |
| outputs01 | 4: valid, ZLP, stall, descriptor byte | ABC PDR PASS, unbounded | 5.627 s |
| spacing01 | 3: two-edge settling, length, complete decode | ABC PDR PASS, unbounded | 9.032 s |

Measured on base `2504a318de0931087963b37ff8b6381cf38dc6be` plus receipt-bound
sources. Commands:

```text
python tools/env/run.py run -- python hw/ip/usb/formal/sampling.py --output build/plan03/usb-closure/lookahead03 --regmap build/plan03/fast01/fast/usb/regmap/usb_regs.json --role lookahead --portfolio
python tools/env/run.py run -- python hw/ip/usb/formal/sampling.py --output build/plan03/usb-closure/outputs01 --regmap build/plan03/fast01/fast/usb/regmap/usb_regs.json --role outputs --portfolio
python tools/env/run.py run -- python hw/ip/usb/formal/sampling.py --output build/plan03/usb-closure/spacing01 --regmap build/plan03/fast01/fast/usb/regmap/usb_regs.json --role spacing --portfolio
python tools/env/run.py run -- python hw/ip/usb/formal/sampling_witness.py --output build/plan03/usb-closure/sampling-witness09 --lookahead build/plan03/usb-closure/lookahead03/result.json --outputs build/plan03/usb-closure/outputs01/result.json --spacing build/plan03/usb-closure/spacing01/result.json --simulate
```

The witness runner authenticates solver models/configurations/statuses, reimports
authenticated HDL, replays observer binding/canonical lowering and requires exact
equality with the proved models. It does not trust intermediate JSON merely
because it is beside a receipt. Removing observers recovers the exact production
graph. Simulation samples the same clocked assertion/cover predicates at their
original edges, with USB traffic driven only through public ports.

`sampling-witness09`: `WITNESSES-PASS`; its `testOnly
deadhorse.usb.UsbSamplingSpec` subcommand passed all six tests in measured
72.180 s. Six cover bits are observed before/after bus reset: lookahead use,
SIE output/data use, valid/short/overlong SETUP admission and CRC error handling.
Additional wire scenarios exercise active-transfer SETUP preemption, VBUS
loss/reconnect and root reset/release after traffic.

Five actual DUT faults trigger the unchanged predicates: next-cursor,
descriptor-data and decoded-length captures held at reset values; descriptor
capture misphased to `ce && sie.in_ready && sie.tx_ready`; decoded-length
capture misphased to `ce && outReady && !outValid`. Phase faults capture on the
consuming edge, exposing stale values. Graph checks permit only the selected D
connection and fault logic to change; consumers, clocks, resets and references
are preserved.

## Preserved failures and diagnostic debt

Initial Z3 `lookahead02` timed out after measured 121.896 s under the unchanged
120 s solver cap. Induction passed; base checking reached step 34. The single
portfolio rung above closed it; no unchanged timeout retry occurred.

Initial witness emission failed because of a keyword port and generated
unmapped/width-mismatched expressions. Standard Yosys techmapping repaired
emission without relaxing Verilator warnings. `sampling-witness06` did not
detect a one-sample extra stage or EOP delay reduction from seven to one;
these were inadequate mutations, not qualified negative controls.
`sampling-witness07` showed `sie.in_ready` alone remains high between byte
acceptances; the corrected phase fault includes `sie.tx_ready`. Failure evidence
is preserved. The reconnect fixture initially omitted the existing host attach
wait and was repaired to use that same wait, without changing a deadline.

The seventh newly authored diagnostic cover asks for a new SETUP while still
collecting a nonempty previous SETUP header. It has not been reached. One
PDR/Z3 attempt to prove the conjunction impossible timed out after measured
121.251 s (`sampling-abort-diagnostic01`, depth 48, cap 120 s). It is
**unresolved**, not proved unreachable; do not rerun unchanged. It remains in
source/inventory. No safety assertion depends on this extra conjunction, and
the actual safety-use guards/reset/error/abort scenarios have witnesses above.

Independent reviewer `plan03_consolidation_review` reviewed the predicates,
binding, replay and fault repairs, and accepted retaining this extra diagnostic
as visible debt without weakening the eleven assertions.

The wrapper-context proof now passes (`sampling-wrapper-context03`): all
232 matched state transitions, clock/reset functions and common outputs agree
for arbitrary current state and inputs after removing only the standalone
engine's unused `txEmpty`/`rxEmpty` observation ports. The actual next-cursor
D-input fault is rejected. Independent review accepted that scope. Command:

```text
python tools/env/run.py run -- python hw/ip/usb/formal/resume_equivalence.py --engine-context --before build/plan03/usb-closure/lookahead03/emit/engine --after build/t19/sie-wrapper-binding-03/emit/usb --output build/plan03/usb-closure/sampling-wrapper-context03
```

Evidence collection requires complete source, model, script, log and scenario
inventories, checks all hashes and revalidates solver assertions. The separate
`sampling-runtime-archive02` preserves the six compiled simulation fixtures,
executables and execution records. Chisel's exported fixture differs only in
terminal LF count; both exact file hashes are retained. Missing/mixed inventory,
empty cover metadata and mismatched log markers are rejected.

### Optional diagnostic triage record

Measured model statistics come from
`sampling-abort-diagnostic01/positive/job/model/design.log`, produced by the
diagnostic runner's Yosys `stat`. They describe the prepared model, not chip area.

| Item | Evidence |
| --- | --- |
| Prepared size | 1,844 cells, 8,156 wire bits, 808 FF bits, six memories totaling 384 bits |
| Requested depth / cap | 48 / unchanged 120 s |
| Reached | PDR frame 47; no trace or proof before timeout |
| Growth runs | Not run; no further diagnostic budget spent |
| Smallest reachable cover depth | Unknown; no reachability claim |
| Unneeded state | Complete production engine retained; no abstraction added |
| Rung / outcome | One PDR/Z3 portfolio attempt, unresolved after measured 121.251 s |

This optional conjunction remains visible debt. No original sampling claim is
replaced by it. The complete USB aggregate and boundary qualification remain open.

## Timing qualification

Fresh `tools/timing/check.py` runs authenticate the sampling manifest, audit
OpenSTA's exported setup/hold pin-pair relation against the register certificate,
and reject unapproved timing overrides or clock exclusions. For every populated
class, an actual mapped launch is delayed through 160 identity buffers. The
reported path must traverse the entire inserted chain, exceed both its class
ceiling and original delay, and fail the production acceptance classifier.
Wrong setup/hold multipliers, missing pairs, wrong capture pins, false paths and
clock-group bypasses are rejected. No timing exception is inferred by hand.

| Measured receipt | Mapped area µm² | Populated classes / rejected delay faults | Sampling / exception qualification | Overall |
| --- | ---: | ---: | --- | --- |
| qualified-control05 | 46,165.056 | 7 / 7 | PASS / PASS | PASS |
| qualified-engine01 | 160,227.648 | 10 / 10 | PASS / PASS | FAIL: two pad hold rows |
| qualified-usb01 | 197,379.2128 | 17 / 17 | PASS / PASS | FAIL: four pad hold rows |

Measured by `python tools/env/run.py run -- python
scratch/plan03_qualified_control05.py` and the `engine`/`usb` invocations of
`scratch/plan03_qualified_integrated.py`. Those drivers invoke
`tools/timing/check.py --operating-point usb-48mhz --usb-cadence
build/plan03/fast01/fast/usb/formal/result.json --usb-sampling
build/plan03/usb-closure/sampling-manifest.json`, selecting the matching top and
all HDL files from `lookahead03/emit/<block>`. Engine/wrapper additionally use
`--usb-equivalence build/plan03/preenable-fixture-fix01/result.json`.
The precise commands, source hashes, class paths/budgets and fault artifacts
are in each receipt and its `commands.jsonl`.

All three have zero electrical violations. Engine/wrapper setup status is
**warning**, within the unchanged approved ceilings; their remaining pre-layout
pad hold slack is measured **−0.102503 ns**. Routed hold/removal is separately
reported in the physical report. Independent review verified the complete
class/fault inventories and artifact/HDL hashes and accepted these narrow
qualifications. It did not accept the aggregate or physical signoff.
