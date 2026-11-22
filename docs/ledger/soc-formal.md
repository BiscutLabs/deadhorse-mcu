# SoC formal evidence

## T20 GPIO/ADC/timer logical contract — 2026-11-21

Measured on `72bcfacc0916b6c00d54f5c4518ab16aa46c5a47` plus the source-hashed
working tree, command:
`python tools/env/run.py run -- python3 hw/top/reference/formal/check_inactive.py --output build/t20/i1/pin-contract-proof`.
The prior three static-pad claims remain, extended with GPIO, timer and ADC
safety, for six assertions in one unbounded ABC PDR job. No reset masking or
environment assumptions. Positive command time is measured 0.27 s including
startup, rounded from the receipt. The all-inputs-high Z3 cover passes in
measured 0.42 s; each of four independently enabled actuator/GPIO/timer/ADC
faults fails its expected assertion in measured 0.32 s (rounded).

`build/t20/i1/pin-contract-proof/result.json` records commands, source/artifact
hashes, exact fault identities and unrounded times. Independent review checked
all hashes and the actual tie-off-module binding. This is a logical inactive
interface proof, not a functional peripheral, analog pad or whole-SoC proof.

## T20 inactive logical pad boundary — 2026-11-21

Measured on `72bcfacc0916b6c00d54f5c4518ab16aa46c5a47` plus source-hashed
local changes, command:
`python tools/env/run.py run -- python3 hw/top/reference/formal/check_inactive.py --output build/t20/i1/inactive-proof-3`.
Receipt `build/t20/i1/inactive-proof-3/result.json` binds the harness, real
static tie-off module, runner and emitted artifacts. Independent review checked
the hashes, port binding, assertion identities and actual fault witness.

| Original safety requirement | Kind / engine | Assumptions | Measured time |
| --- | --- | --- | --- |
| QSPI data/clock inactive, selects high, all enables zero | proved / ABC PDR | none | 0.265 s shared job |
| Actuator outputs and enables zero | proved / ABC PDR | none | same job |
| JTAG TDO and enable zero | proved / ABC PDR | none | same job |

Times measure the complete SBY command including startup. The unconstrained
all-inputs-high cover passes in measured 0.316 s with Z3. Enabling one actual
actuator output fails the actuator assertion with a Z3 counterexample in
measured 0.316 s. This is not a whole-chip proof or pad timing measurement.
Static outputs need no reset premise and remain safe without service clocks.

The first attempt failed emission because optimization folded constants and
static assertion lint rejected the injected fault; the second failed assertion
lowering before a solver ran. Both remain under `inactive-proof` and
`inactive-proof-2`. The final fixture disables optimization/static lint and
uses the standard assertion lowering, retaining every property and no assumptions.

## T20 I1 control composition — 2026-11-21

Measured on `72bcfacc0916b6c00d54f5c4518ab16aa46c5a47` plus the local,
source-hashed main working tree. This is focused composition evidence, not
complete T20 acceptance. No CI, solver cap change or inherited-proof waiver.

Command for each row:
`python tools/env/run.py run -- python3 hw/top/reference/formal/check_i1_control.py --block BLOCK --output build/t20/i1/OUTPUT`.
Times below are measured monotonic elapsed time for the positive SBY command,
including startup, as recorded in `result.json`.

| BLOCK | OUTPUT | Emitted assertions | Result / engine | Measured positive time |
| --- | --- | --- | --- | --- |
| error | proof-error-final | 6 | proved, ABC PDR | 0.365 s |
| slot | proof-slot-final | 11 | proved, ABC PDR | 0.516 s |
| memory | proof-memory-2 | 12 | proved, ABC PDR | 8.776 s |
| nested | proof-nested-final | 2 | proved, ABC PDR | 0.365 s |

Every row also has PASS Z3 covers and a required FAIL Z3 actual-fault control
with a concrete witness. Emitted counts include production helper assertions;
they are not a count of independent architectural requirements. The runner
checks exact module inventories and meaning-to-label bindings by harness hash.

Assumptions/premises and qualification limits are listed in
[the formal README](../../hw/top/reference/formal/README.md). Both resets start
asserted. Error/slot/memory employ a stable, one-outstanding generated bus
requester; slot uses a real finite error backend. Nested uses unrestricted
upstream requests and a legal variable-latency endpoint model. No RAM integrity,
full-top CDC, physical reset or unrestricted downstream liveness proof is claimed.

The negative controls invert error response-valid, slot response-valid and
loader completion, and force nested quiet high. Hierarchical failure identity
is retained, including `credit.assert__chisel3_builtin_0` and
`d.assert__chisel3_builtin`; a missing mandatory or unexpected fault fails closed.
The nested 32-step covers reach normal response/drain, not the production
128-edge watchdog. Separate simulation holds the endpoint response beyond both
nested watchdogs, checks exactly one upstream error and verifies fresh traffic
cannot receive the stale response.

Preserved diagnostic errors: error-1 counted the two explicit reset-init
assumptions as unexpected; error-2 lowered clocked checks before `async2sync`;
memory-1's intended fault produced a witness but a backward wall-clock jump
caused SBY status ERROR; nested-1 rejected its hierarchical fault name through
the old shared parser. None is reported as a pass. These were tooling errors,
not timed-out proof retries or relaxed properties. Independent review prompted
exact inventory and hierarchical fault checks before the final runs.

## T21 focused functional I/O proofs — 2026-11-21

**Measured** by pinned command `python3 dv/soc/check_io_formal.py --output
build/t21/formal-frozen` on HEAD72bcfacc0916b6c00d54f5c4518ab16aa46c5a47 plus
source-hashed uncommitted changes. Receipt `build/t21/formal-frozen/result.json`
is PASS, with generated input/configuration, model, log and witness hashes.

| Job | Result | Engine | Measured seconds | Controls |
| --- | --- | --- | --- | --- |
| main8 | proved | abc pdr | 0.567 | cover + intended fault PASS |
| main9 | proved | abc pdr | 0.516 | cover + intended fault PASS |
| aon | proved | abc pdr | 0.565 | cover + intended fault PASS |
| wake | proved | abc pdr | 0.266 | cover + intended fault PASS |
| gpio_denied | proved | abc pdr | 0.466 | cover + intended fault PASS |
| adc_denied | proved | abc pdr | 0.566 | cover + intended fault PASS |
| adc_scale | bounded to16 edges | btor btormc | 1.767 | cover + intended fault PASS |

Initial reset low then arbitrary is the only formal assume; inventory checks
require exactly one. Denied jobs map0to1 against owner0, covering all denied
tags. GPIO owner safety ties the clocks, not an asynchronous transport proof.
Timer jobs prove update consistency/output-mode safety, not independent full
cadence/wake delivery; directed simulation covers ratios, exact expiry,
collisions and stopped-main wake. GPIO wake covers acknowledgement, pending
stickiness, apply-time level match and explicit disarm; later-level/clear
priority also has simulation. ADC scaler checks one arbitrary12-bit sample,
completion after twelve steps and exact floor(raw×25300/4095); bounded16 only.

All intended actual RTL faults rejected, with exact property identities and
concrete witnesses. Initial emission/layer/expected-owner-label errors were
fixed with failed evidence preserved; no solver timeout or assumption change.
See each IP formal README and the T21 report. Neither CI tier was run.

## T28 lite-first digital release — 2026-11-21

**Measured** by `python tools/env/run.py run -- python dv/soc/check_boot_control.py
--output build/t28/frozen01`, formal subcommand
`python hw/ip/boot_control/formal/check.py --output build/t28/frozen01/formal`,
on main HEAD72bcfacc0916b6c00d54f5c4518ab16aa46c5a47 plus receipt-hashed local
sources. Formal receipt PASS; neither CI tier runs.

| Model | Assertions | Result | Engine | Measured seconds |
| --- | --- | --- | --- | --- |
| BootRelease control recurrences/qualification | 4 | proved unbounded | abc pdr | 0.265 |
| BootControl denied-origin containment | 2 | proved unbounded | abc pdr | 0.366 |

Initial epoch reset low is the only formal assume. Subsequently independent
epoch/service resets and inputs are arbitrary. Owner stimulus maps origin0
to1, retaining every denied tag1..7; it does not prove legal-owner liveness.
There are no software protocol/stability assumptions. Control covers seen
before release, released during service reset and error; owner covers denied
response and START during grant. All finite covers and early/key/owner actual
RTL faults pass receipt validation, including expected failed identities.
The existing120-second cap and witness depth12 are unchanged.

Stopped-clock whole-reset assertion, command cancellation at both accepted
transport stages, legal/repeated keys and two-core loader handoff have focused
simulation coverage. This is not an unbounded whole-SoC or analog reset proof.
See the T28 report and hw/ip/boot_control/formal/README.md for exact scope.
