# I2C formal scope

`python tools/env/run.py run -- python3 hw/ip/i2c_host/formal/check.py
--json build/t17/regmap/i2c_host_regs.json --output build/t17/formal-new`
emits fresh models. Aggregate acceptance generates the register map first.
The table lists obligations and configured bounds, not pass claims. Current
results are recorded in `docs/ledger/i2c-formal.md`: WRITE, READ and RECOVER
correctness jobs remain unproved after timeout; TIMEOUT is bounded to 160
edges and denied-access safety is proved. WRITE's actual fault is rejected;
READ and RECOVER formal faults and completion covers remain unresolved.

| Role | Claim | Method and scope |
| --- | --- | --- |
| write | Nine clocks, MSB-first data, ACK result, completion/event, minimum low/high durations and stable SDA during high | Bounded 320 edges; scripted START then one arbitrary WRITE byte; peer ACK |
| read | Nine clocks, released SDA for data, chosen ACK/NACK, received byte/valid, completion/event and waveform minima | Bounded 320 edges; scripted START then one arbitrary peer byte and arbitrary ACK/NACK choice |
| recover | Nine recovery clocks followed by STOP/free, released idle outputs, done/recovered events | Bounded 256 edges; peer releases both lines |
| timeout | Stuck-pin START exits, releases outputs, clears ownership and records timeout | Bounded 160 edges; one arbitrary choice of SCL or SDA held low, status repeatedly polled |
| denied | Exact response accounting, error/zero readback and observable disabled-state preservation | Unbounded ABC PDR; owner0 and all denied tags1..7; arbitrary request/address/data/strobes |

The protocol cases use HOLD1/LOW4/HIGH4/FREE4 and timeout64 (timeout8 for
the timeout case). The MMIO master programs and applies this tuple before the
operation. Payload and READ ACK/NACK are captured at a public bus grant.
The pin peer is an independent wired-AND model, advancing from observed SCL
edges. No production internal state is read. Sleep may change arbitrarily
after public clockHold confirms admission; sleepEnable is false.

All outcomes are checked through pins and MMIO. Completion must occur by
edge 310 for WRITE/READ, 245 for RECOVER, or 145 for TIMEOUT; these deadlines
leave explicit checking margin within the approved bounds and prevent an
implementation that never completes from passing vacuously. Normal frame
edge counts freeze after the final event read so a later owned-idle timeout
is not misclassified as a tenth byte clock. A single assertion conjunction
contains every obligation in each model; the runner checks its cell count.

Each protocol role has two completion covers (A5 and observed sleep during
admitted active work, or both
stuck-pin choices for TIMEOUT); READ additionally covers both ACK and NACK
completion explicitly. Denied covers exercise an error response and
an error response while another request is present. Actual production-path
mutations invert WRITE pull-low data, corrupt received bit0, suppress the
recovered event, suppress timeout expiry, or bypass ownership respectively.
Each must produce a concrete counterexample. BTOR btormc checks bounded,
cover and corrupt models; ABC PDR checks the denied model.

Initial reset is low and subsequently arbitrary, subject to the qualified HF
reset contract. There are no Chisel assume statements; scripted master and
peer connections are the environmental restrictions above. No external
stretching is modeled in WRITE/READ/RECOVER. The denied harness maps raw
origin0 to1, covering all seven disallowed origins against owner0.

These checks do not prove arbitrary firmware sequences, every timing tuple,
exact timeout boundary or chatter behavior, arbitrary ownership transfer,
multi-controller arbitration, physical bus timing, analog filtering or
metastability. Independent pin/reference tests cover additional sampled
scenarios. Bounded results are never called unbounded proofs.

Every formal job has one 120-second attempt. A timeout remains explicitly
deferred/unproved under existing user direction. Tool errors and real
counterexamples fail acceptance and are never treated as timeouts.
Fresh TIMEOUT status must agree with solver exit code 8; contradictory exit
codes fail closed.

`deferrals.json` is reviewed retention policy for actual timeout attempts,
not a successful proof receipt. Before retaining an entry, the runner freshly
emits the model and matches every source hash and the full role/variant,
engine, mode, depth, property count, scope, 120-second budget, pinned
environment and formal-flow identity. A mismatch fails closed for focused
review and a justified changed-model attempt. There is no automatic adoption
of changed models or new timeout entries.
Only environment-lock line endings are normalized: LF and CRLF are hashed in
the historical CRLF representation, preserving the reviewed policy identities
on either checkout. Every other lock byte remains bound. Emitted-model and
original-evidence hashes remain byte-exact.

T32 records one exact additive environment-lock transition for OpenOCD: the
original `f71eed...` lock and current `250c90...` lock are both authenticated.
Removing only the pinned OpenOCD/Jim sources, OpenOCD version/configuration and
three build packages must reconstruct the exact original lock hash. All older
tool pins, archives, base image and package snapshot remain identical. Every
other job/model field must still match. This is not a general environment
exception or a claim of identical rebuilt binaries. New rows retain the actual
current environment hash, the original identity/provenance and the explicit
compatibility record. All eight obligations remain unproved and are not rerun.
Tests reject other lock changes, forged current hashes, changed model/job fields
and tampered historical evidence.

The policy records original receipt, solver status and log hashes. When those
ignored build artifacts are present, their hashes and timeout identity are
checked. A fresh checkout may lack historical build output; its receipt lists
that provenance as unavailable while still requiring an exact freshly emitted
model/job match. Retained rows explicitly say `solver_rerun=false` and remain
`deferred_unproved`; no solver execution, witness or proof is fabricated.
Successful checks continue running. `test_formal_deferrals.py` exercises
changed models/jobs, malformed policy, tampered evidence and missing-history
reporting using temporary files beneath `build/`.

The initial run's WRITE/READ emissions preceded the repeated-START guard
repair. Their old-model timeouts are excluded from retention; those changed
models received one fresh attempt after the repair. The reviewed policy now
retains their five actual final-model timeouts and RECOVER's three initial
timeouts, whose emission already included the repair. All eight entries stay
unproved and apply only when the freshly emitted model and job match exactly.
