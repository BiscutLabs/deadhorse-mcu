# T19 USB formal ledger

## D48/D50 preflight (2026-11-18)

Decision D48's literal reset-inclusive value-change invariant has a concrete
counterexample on production EP0. **Measured** diagnostic command at
`15161bf897d1b4b4cba69030154daf89ee19ca12`:
`python tools/env/run.py run -- python3 scratch/t19_value_reset_probe.py`.
Receipt and trace: `build/t19/d48-reset-probe-02/`. The exact emitted
`UsbControl.sv` SHA-256 is
`c772e4c749448130391c26e51864269ce2473d29c7255a861b8c039af3fe71ab`.
The diagnostic retains production sequential logic and adds an unreset
previous-value/previous-enable monitor initialized only at formal startup.
The actual emitted `UsbBitEnable` drives the common enable; packet-interface
inputs are synthetic, as in the standalone control harness, not a full
SIE-composed wire trace. The earlier `-01` used an enable too early after
release and is retained only as an invalid-production-cadence diagnostic.
Yosys `async2sync` and SAT find a bounded counterexample: an enabled SETUP
admission changes state to setup, then reset assertion returns it to idle
with both the preceding and current enable low. This witness changes state
bits zero/one, not the failing timing endpoint state[5]; it refutes the vector
invariant and does not substitute for a bitwise state[5] eligibility proof.
The state aliases bind to
the existing mapped scalar Q pins in the receipt. This sampled witness
refutes the invariant; it is not a proof covering every inter-edge reset.
No reset exclusion or additional assumption has been accepted.

Independent source review also identifies EP0's synchronous bus-reset
override as potentially non-idempotent on its first non-enable edge: the
PHY registers bus reset on an enabled edge and EP0 observes the new value
on the following sample edge. Repeated identical reset writes do not resolve
that first value change. This source-derived finding is separate from the
executed root-reset counterexample.

D50 small-model preflight is **not eligible**. Production constructors take
only proof hooks/memory injection, not size parameters. Both buffers hard-code
wrap at 64 and seven-bit pointers; the memory hard-codes nine eight-byte banks,
seven-bit addresses, slices `(2,0)` and `(6,3)`, and bank bound nine. The formal
harness also fixes capacity 65, packet limit 64, pointer bounds and distance
arithmetic. Fixed byte width eight, four-cycle cadence, three read stages and
service bounds are additional non-scaling protocol/timing constants. These
are source constants, not measured performance figures. Substituting a small
memory would not shrink the control ring. Independent review confirms that
an actual small instance requires prohibited RTL parameterization/restructuring.
No small-model solver job was launched; its time box was not started.

Checkpoint results preceding the D45 follow-up are **measured** at Git base
`a280df4fa17516a2ac8507628a6f12e3c4128895` plus uncommitted T19 sources.
Emitted source hashes in each receipt identify the actual checked model.
They do not certify later source changes. T19 remains incomplete.

Commands below are prefixed with `python tools/env/run.py run --`.

| Contract | Actual result | Receipt / command |
| --- | --- | --- |
| Byte-width shared FIFO ordering, retention, reset and Gray/release safety | Unbounded ABC PDR pass; reachable covers and data/Gray/reset faults rejected | `python3 hw/lib/formal/cdc_proof.py --width 8 --depth 2 --output build/t19/formal-cdc-01` |
| Production four-sample cadence | Unbounded ABC PDR pass; cover and early-enable fault pass | `build/t19/formal-02/cadence/`, from `python3 hw/ip/usb/formal/check.py --json build/t19/regmap/usb_regs.json --output build/t19/formal-02` |
| Non-owner accesses cannot produce side effects | Unbounded ABC PDR pass; covers and bypass-owner fault pass | `build/t19/formal-02/denied/`, same command |
| Reduced-threshold host-resume capture/retention | Unbounded ABC PDR pass; cover and dropped-wake fault pass | `build/t19/formal-resume-final/resume/` |
| EP0 address/configuration side-effect qualification | Unbounded ABC PDR pass; reachable address/configuration/replacement-SETUP covers and premature-status fault pass | `build/t19/formal-control-final/control/`; this does not establish packet-boundary phase equivalence |
| Raw reset/VBUS pad safety | Unbounded ABC PDR pass; active-reset cover and ignored-reset fault pass | `build/t19/formal-lane-01/pads/` |
| Retained SIE register-enable implication | Yosys SAT pass with arbitrary register values/PHY outputs; always-enabled prepared-register fault rejected | `python3 hw/ip/usb/formal/sie_enable.py --output build/t19/sie-enable-03` |
| IN accepted-byte integrity, replay/commit, stability and service | **Unresolved**; full-byte and lane-zero proofs timed out | `build/t19/formal-in-01/`, `formal-portfolio-01/in/`, `formal-in-lane-02/in_bit0/` |
| OUT packet commit/rollback, byte integrity, stability and service | **Unresolved**; full-byte and lane-zero proofs timed out | `build/t19/formal-out-01/`, `formal-portfolio-01/out/`, `formal-lane-01/out_bit0/` |

The packet-buffer covers reached concrete witnesses, and planted missing
commit/publish faults produced counterexamples. The latest IN lane-zero job
also reached its service cover and rejected permanently withheld valid.
These are not substitutes for the unresolved positive proofs. One bit lane
does not establish byte-wide integrity; the other lanes were not swept after
lane zero timed out.

## Timeout diagnosis

The initial ABC PDR jobs retained the existing 120-second solver cap. The
portfolio added Z3 induction without changing assertions, assumptions or the
cap. The final cone-reduction diagnostic checks one named data bit while
retaining the actual byte-wide RTL and all control assertions; it also timed
out. No timeout is accepted as a deferral or a bounded proof.

Measured prepared original models contain 304 cells/nine memories (IN) and
316 cells/nine memories (OUT), from independent pinned Yosys `stat -width`
inspection of the preserved `design_prep.il`. The symbolic oracle removes the
need for a second full reference RAM, but the DUT RAM remains in the proof.
For the IN portfolio, Z3 basecase logs reach step twelve in under a second,
step twenty-four around seven seconds, and step thirty-five around 108
seconds; these are solver log timestamps, not separate completed BMC jobs.
Initial IN cover witnesses reach at most twenty-three steps; OUT at most
seventeen. No bound was reduced or reported as unbounded.

Further proof engineering needs an explicit scoped plan under the formal
timeout-triage workflow: separate the control/service conjunction from
integrity, and consider independently proved helper invariants or a sound
arbitrary-entry abstraction. Freeing RAM data for a byte-equality assertion,
assuming DUT valid, increasing the timeout, or dropping an assertion is not
an acceptable repair.

See [the harness contract](../../hw/ip/usb/formal/README.md) for every input
restriction and abstraction. Digital proofs do not establish analog CDC,
physical reset recovery, USB electrical compliance or whole-system wake.
The SIE certificate alone does not authorize multicycle timing.
## D45 follow-up: reset cadence and packet-proof triage (2026-11-18)

At baseline `38e0bddb691288eeba92cb257d30935a40c15fb6` plus working changes,
`python tools/env/run.py run -- python3 hw/ip/usb/formal/check.py --json build/t19/regmap/usb_regs.json --case cadence_reset --output build/t19/d45-cadence-05`
**measured** PASS for covers, two-cycle-enable fault rejection and both
unbounded ABC PDR assertions. The monitor history survives DUT reset and is
initialized only in the initial formal state. Reset is initially low and
then arbitrary. Assertions establish no enabled captures less than four
sample edges apart and four prior reset-released edges before a capture.
This is not yet a binding of the cadence to a measured combined engine.

Independent reviewer step-0 command:
`python tools/env/run.py run -- python3 scratch/t19_packet_step0_review.py`.
Prepared-model statistics were corrected using `--stats-only`, without
repeating solver jobs. Evidence: `build/t19/packet-step0-review-01/result.json`.
The table's counts, times and solver results are **measured** diagnostics.

| Step-0 measurement | IN lane zero | OUT lane zero |
| --- | ---: | ---: |
| Prepared cells | 340 | 319 |
| Sequential state bits, including `$anyinit` | 261 | 244 |
| Memories / storage bits | 9 / 576 | 9 / 576 |
| Quarter-depth BMC (12) | PASS, 0.6167 s | PASS, 0.4662 s |
| Half-depth BMC (24) | PASS, 5.9731 s | PASS, 4.6210 s |
| Preserved depth-48 portfolio | TIMEOUT, 121.3632 s | TIMEOUT, 121.1839 s |
| Preserved earliest cover bounds (zero-based) | 14, 22, 18, 22 | 15, 10, 16 |

These bounded passes do not close any unbounded acceptance requirement.
The original solver cap remains 120 s; measured wall time includes shutdown.
Full-byte Z3 reached step 35, lane-zero step 36 before timeout. Queue control,
service and symbolic-data integrity remain coupled to the storage model.
All original assertions and reset/input assumptions were retained.

Baseline ABC is followed by rung 1 (portfolio) and rung 4 (exact lane split),
both unresolved. One of the three permitted rungs remains. The proposed
remaining rung 3 is arbitrary-entry memory abstraction with real control and
an exact tracked-entry read/write contract; equality-relevant data must not
be freed or valid assumed. It was not attempted before the new timing stop.
If unresolved, stop: the smallest expected next approach is proved
pointer-distance/occupancy and read-pipeline invariants (rung 6, requiring
approval). No unchanged timed-out job was rerun, no acceptance label changed,
and no new unbounded packet proof is claimed.

## D47 scoped sparse-memory and ownership attempt

User approval: up to 45 minutes, unchanged assertions, assumptions, bounds,
solver caps and acceptance. The attempt ran from 2026-11-19 02:12:29 UTC to
02:54:54 UTC (local date 2026-11-18), **measured** by the session clock;
elapsed time is **estimated** by subtraction as 42 minutes 25 seconds.
No further positive packet-proof jobs were launched after this stop.

The step-0 table above is retained. D47 extends the prior portfolio/lane split
with a sound sparse-memory refinement and asserted helper invariants. This
was one time-boxed proof-engineering attempt with changed model iterations,
not permission for unchanged retries. All original six assertions per buffer
and their input restrictions remain unchanged. Helpers inspect proof-only
state, add no assumptions, and are themselves required to prove.

The table is **measured** from source-bound job receipts at baseline
`38e0bddb691288eeba92cb257d30935a40c15fb6` plus their recorded working models.
Each command is `python tools/env/run.py run -- python3 hw/ip/usb/formal/check.py
--json build/t19/regmap/usb_regs.json --case <case> --output build/t19/<run>`,
combining the listed cases for that run. Sparse03 through Sparse06 also use
`--portfolio` (ABC PDR plus Z3); other rows use ABC PDR. Every solver cap stays
120 seconds, prove depth setting 48; elapsed wall time includes preparation
and shutdown. TIMEOUT is unresolved, not a design failure or a bounded pass.

| Run | Case | Positive result | Measured wall s |
| --- | --- | --- | ---: |
| `d46-helper-01` | `out_helpers` | TIMEOUT | 121.329 |
| `d46-helper-02` | `in_helpers` | TIMEOUT | 121.275 |
| `d46-sparse-01` | `in_sparse` | FAIL | 0.671 |
| `d46-sparse-01` | `out_sparse` | TIMEOUT | 121.875 |
| `d46-sparse-02` | `in_sparse` | TIMEOUT | 121.718 |
| `d46-sparse-02` | `out_sparse` | TIMEOUT | 121.180 |
| `d46-sparse-03` | `in_sparse` | TIMEOUT | 121.465 |
| `d46-sparse-03` | `out_sparse` | TIMEOUT | 121.106 |
| `d46-sparse-04` | `in_sparse` | TIMEOUT | 121.612 |
| `d46-sparse-04` | `out_sparse` | TIMEOUT | 121.192 |
| `d46-sparse-05` | `in_sparse` | TIMEOUT | 121.362 |
| `d46-sparse-05` | `out_sparse` | TIMEOUT | 121.351 |
| `d46-sparse-06` | `in_sparse` | TIMEOUT | 121.116 |
| `d46-sparse-06` | `out_sparse` | TIMEOUT | 121.961 |

Initial sparse-model failures were spurious: the IN trace replay on the real
production memory passed (`python tools/env/run.py run -- python3
scratch/t19_replay_sparse.py`, `build/t19/d46-replay-01`). The model was corrected
to reproduce registered-address/current-array read semantics followed by two
data stages. The first refinement cover erased unused real RAM; corrected
covers explicitly observe both real and sparse outputs. These failed drafts
remain preserved. Helper01 also contains an emitter/source-change failure;
its aggregate receipt is not accepted. Sparse03's OUT helper omitted the
rejected-packet guard; it was corrected before later attempts, without changing
any original assertion.

Final memory refinement command:

```sh
python tools/env/run.py run -- python3 tools/sbt.py "runMain deadhorse.usb.EmitUsbMemoryRefinement build/t19/d46-memory-refine-06/emit"
python tools/env/run.py run -- python3 hw/ip/usb/formal/memory_refinement.py --emit build/t19/d46-memory-refine-06/emit --output build/t19/d46-memory-refine-06/proof
# cover PASS; corrupt FAIL; correct PASS (unbounded ABC PDR)
```

The binding selects actual production RAM words through muxes, removes only
the three witness-input drivers, rejects missing/aliased words, and adds no
assumptions. The read-phase mutant adds a sample edge. Independent review
reran the earlier identical functional refinement and verified its binding
and the common-reset harness warmup scope. Later receipts also bind Scala/script/emission hashes
before and after execution. This proves the memory simulation relation, not
the unresolved packet-buffer contracts.

Final Sparse06 real-model covers and missing-commit/publish/withheld-valid
fault controls pass; both positive jobs time out. Induction-only traces expose
unreachable helper states, not demonstrated production counterexamples.
Independent review confirms the original assertions/guards/bounds are intact.
Fresh default production emission (`EmitUsb build/t19/d46-production-hook-review-01`)
is byte-identical for every IN/OUT RTL file to both `d46-emit-02` and `emit-13`.

Smallest remaining candidate change: prove the OUT oracle lifecycle bound
`watching && inPacket => position < queued +& packet`. The final induction
trace starts with queued=4, packet=37, position=46, then publishes a watched
position beyond committed occupancy. This is an unreachable-start diagnostic.
IN has no new counterexample; Z3 was still working at induction step 38.
The next expected approach is to prove oracle/control helpers independently
with the irrelevant RAM cone removed, then compose data ownership while
retaining every original assertion in the proof union. This is proposed,
unmeasured work, not a guaranteed closure or an approved further attempt.

The aggregate retains packet proofs as blocking unresolved obligations. It
refreshes real-model covers/faults through `--controls-only`, which explicitly
returns nonzero/unresolved and cannot grant acceptance. Positive timed-out jobs
are not silently repeated, skipped into a pass, or accepted as deferrals.

Independent final review identifies a remaining reset-composition gap: the
proof harness resets cadence and buffers together; production inRelease and
outRelease can reset buffers while engine cadence continues. Therefore
`CE => memoryAge == 3` is only common-reset harness evidence. A proposed next
proof must qualify warmup by actual IN-valid/OUT-RAM capture and establish
the retained SIE consumption/reset contract. This is unmeasured, unresolved
work outside the exhausted D47 attempt; no additional positive job was run.

## D48 frozen verification

Command `python tools/env/run.py run -- python3 hw/ip/usb/check.py --output
build/t19/d48-frozen-check-01`, base `15161bf897d1b4b4cba69030154daf89ee19ca12`
plus frozen source hashes, runs all eight non-packet cases with unbounded
proofs, covers and faults successfully. `reset_data` compares the shared
ResetRelease/CdcSync cone's old raw-reset expression with its synchronized
data expression, and checks reset assertion; its early-bypass fault fails.
This is sampled digital evidence with asynchronous-reset lowering, not an
exhaustive inter-edge or physical skew claim. Wire/MMIO/reset/resume tests
pass; byte-width CDC passes. Packet controls/covers pass, but positives stay
unresolved and no unchanged timed-out job was rerun.

Local D48 source/mapped invariants prove for unreset headers with no reset
masking. Other resettable registers are conservatively full-rate, not proved
ineligible bit-by-bit. Value-change, early-release and retained-pin faults
are rejected along with the original faults. Actual enable replica D/CLK/RN
identities bind the unbounded shared-library-FF equality lemma to every copy;
wrong-data and wrong-reset faults fail. The checker uses only those proved
equalities in its otherwise all-Q-free mapped cut. Independent review is clear
for this limited evidence; timing, packet and sampling/exception qualification
remain unresolved. Aggregate and fast CI fail; full tier was not run.
