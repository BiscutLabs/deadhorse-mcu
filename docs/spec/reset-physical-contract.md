# Reset physical contract

T44 / D113; production baseline 5b0cf93814ddfd35bc9bc48258c54068b30b51c4.
This defines the required classification and acceptance. Its implementation
and physical checks remain open in STATUS. It does not claim timing closure.

## Scope and evidence

Keep the cold, warm, debug and USB transport cohorts and the D106/D107
cancellation boundaries. Async assertion remains required when clocks stop.
RAM contents, reset causes and debug retain their existing cohort semantics.
Ibex/FPU reset behavior and regmap reset values remain unchanged.

The classification unit is an asynchronous source-to-pin contribution, not a
signal name. A sink with more than one contributing source has one row per
contribution and a complete combined-source expression. Every mapped RN/SN/
SETN input is accounted for, including constants and functional event inputs.
The inventory also records clock polarity, actual clock source/gating ancestry,
the launch register if present, transparent buffer/inverter paths, mapped and
physical aliases, source hashes, and endpoint load/fanout. Unknown topology,
multiple unresolved drivers or ambiguous aliases fail the audit.

Class A describes assertion edges and is orthogonal to the release class. It
cannot absorb an otherwise unclassified release path. The release classification
is B, C, D or E; the explicitly approved functional-event contributions remain
separate. A proven constant-inactive asynchronous control has no release
transition; inventory it explicitly with its constant-driving evidence, not a
class-B exception. Supply/electrical checks remain. A class D result is a
defect, not an accepted timing category.

## Classes

| Class | Meaning | Timing treatment |
| --- | --- | --- |
| A | Asynchronous assertion, including with a stopped clock | No new assertion exception; retain electrical, minimum-pulse and reset-safe-output checks |
| B | Raw asynchronous contribution to the actual first/second stage of a two-stage ResetRelease or CdcSync | Only its recovery/removal checks may be excluded following structural qualification |
| C | Synchronized release to same-domain ordinary state or an added release pipeline stage | Real recovery/removal checks at all corners; SS/FF are the required T44 measured screen |
| D | Release crossing a clock domain directly into ordinary state | Reject; use a destination ResetRelease, stop if wider architecture is necessary |
| E | Test reset under static shift/capture protocol | Separate tester-mode contract; no T37 scan implementation or production-mode waiver here |

Same-domain requires compatible actual clock edges and gating behavior, not just
the same frequency. Generated main /6 and OSC_IN are distinct domains. For a
gated descendant of a root clock, prove first-edge recovery/removal for every
permitted gate/release sequence. Release while the descendant is stopped is
not itself unsafe when the first resumed edge is adequately separated; do not
introduce new held-reset behavior merely because gating exists. If qualification
fails, a local release repair must still preserve the authorized behavior.
Both AON clock-selection modes require an audited clock binding.

## Class B structural witness

Prove and bind the actual source implementation and mapped stage identities:
the first state drives the second stage's D through only documented synchronous
qualification; both have the required common clock/polarity and asynchronous
source; the released value is the second stage. ResetRelease's existing permit
and first-stage warm-initialization history must be separately recorded. CdcSync
must have the actual two-stage data chain. A name containing `sync` is no proof.

Bindings reject missing, merged, duplicated or ambiguous stage identities and
retain the production source/mapping/library hashes. Never infer a synchronizer
merely because two arbitrary flops happen to be adjacent. Both actual primitive
identity and mapped topology are required. Synchronizer evidence justifies the
specific raw-source recovery/removal exception, not metastability signoff for
the chip or downstream releases.

Generate only qualified source-to-pin exceptions; do not use a clock-group,
domain-wide, reset-net-wide or endpoint-only false path. An endpoint receiving
another synchronized source does not exempt that source. Verify the executed
constraint envelope against the exact intended arc set. If the STA interface
cannot express the required distinction, stop rather than widening it. Data,
clock, electrical and pulse checks remain enabled.

## Functional event inputs (approved 2026-11-27)

The six AON GPIO CdcPulseCapture flags use asynchronous set to retain short
pulses. Their event contribution is listed separately from the cohort-reset
contribution and downstream synchronizers. All existing recovery/removal,
pulse-width and electrical checks remain. No new exception, reset cohort,
event-width assumption or behavior change follows from this listing. Other
unclassified asynchronous controls remain failures.

## Distribution candidate

Keep each two-flop root release. For eligible redistributed sinks, add an
equal-depth tree in the same clock domain. Each added flop has D=1 and its
parent's released Q as active-low asynchronous reset. Assertion propagates
asynchronously through the chain; release advances one edge per level.
Every added stage is class C. It cannot borrow a raw-source class-B exemption.
An initial 32–64 ordinary reset-pin loads per leaf is a design starting point,
not evidence of timing closure; actual capacitance, slew and fanout are checked.

Name the sink set and its root, depth, clock and placement group. Preserve
all reset state, values, polarity and behavior inside the protected core/FPU.
The external release tree may add the latency expressly authorized by T44;
validate boot/order and integration against those delayed inputs without
changing the core/FPU RTL or claiming that old system-level timing evidence
applies unchanged. Place
USB leaves inside the USB group and measure its recovery first. Check equal
release cycles, assertion propagation/minimum pulse, all required release
ordering and startup from stopped clocks. Do not use delay cells or reset hold
buffers as the repair. No physical placement or skew guarantee follows from
equal RTL depth alone.

## Test reset protocol

Test reset is static during shift and capture. Stop clocks at their defined
idle levels. The tester must separate deassertion from the last preceding active
clock edge by the worst applicable removal requirement, accounting for both
clock and reset propagation and the tester window. Only then command reset
inactive with all test enables/mode/pad selections stable. Wait at least N
complete scan periods before the first resumed pulse.
N describes elapsed time with no pulse; it does not silently insert clock
edges. The first legal pulse must satisfy the worst reset-release path delay,
recovery and tester uncertainty across the required corners and polarities,
and subsequent pulses must
respect removal/minimum-pulse requirements.

Use the existing T37 assumed trial period of 100 ns and tester input window
0..1 ns without changing them. The release guard is
`N = max(1, ceil((latest reset arrival + worst recovery + clock uncertainty)
/ 100 ns))`, with all terms taken at the receiving pin and required corner.
The time origin is the tester's deassert command and start of the waiting
interval. Latest reset arrival includes the existing 0..1 ns input window
exactly once. Maximize the numerator over all required corners and active
clock polarities. Ignoring a nonnegative minimum insertion delay of the first
resumed clock edge is conservative; a negative or unknown delay requires an
explicit earliest-edge calculation instead. Recovery to that first edge and
removal from the last preceding edge are separate obligations.
The physical report must publish the resulting integer N and the source of
each term before generating tester constraints. A missing or non-finite term
fails qualification. This is a protocol parameter derived from measurement,
not an extra setup margin or a relaxation of any existing check.

Document separate assertion, waiting and shift/capture phases, including the
static test mux. Do not case-disable reset in a diagnostic recovery/removal
screen and then claim the protocol passes. T37 owns scan implementation and
manufacturing speed; T44 owns this reviewed reset boundary only.

## Acceptance

Audit production mapping and post-CTS cells: no class D, no unapproved reset
logic, all pins accounted for, bound leaf loads, exact class-B arc exceptions.
Negative controls add an actual cross-domain release, combinational gated reset
and ordinary-pin exception. Existing static test mux and documented glitch-free
assertion ORs are the only functional combinational reset logic allowed; buffer
and polarity normalization do not erase their timing or electrical load.

Report raw and classified recovery/removal at SS and FF, in both AON source
modes, plus failing endpoint counts, reset electrical checks and pulse checks.
Zero class-C violations and zero reset-net electrical violations are mandatory.
The after-CTS logic area must be below the user ceiling 5.113576 mm2. Stop for a
remaining class-C failure or no area reduction; non-reset failures stay visible
and are not repaired under this task. Placement-estimated RC is not routed
signoff. Full PVT/MTBF qualification remains a separate all-corner obligation.
