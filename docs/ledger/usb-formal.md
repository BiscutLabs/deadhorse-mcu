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

## D51 reset-aware proof composition, 2026-11-18

Baseline `269fa0f7fe1b0560d58dd62c44ef01340e84b06b` plus recorded source hashes.
`python tools/env/run.py run -- python3 hw/ip/usb/formal/check.py --json build/t19/regmap/usb_regs.json --case cadence_reset --case reset_aware --case reset_aware_early --output build/t19/d51-formal-02`
passes the unbounded ABC PDR proofs, cadence-model covers and missing-suppression/
early-restart faults under the existing per-job caps. Initial reset is low,
subsequently arbitrary; monitor history survives DUT reset. Bus-reset next
data is arbitrary but updates only on the actual production cadence. This is
a sound producer over-approximation, discharged by the source/mapped bus-reset
hold, clock and reset binding; it is not a new environmental assumption.
Both reset-aware lemma cadence emissions must match the cadence_reset proof.

`reset_certificate.py` proves actual source next values and mapped D pins:
normal CE hold, synchronous bus-reset constants, header masking, reset value/
polarity, clock and exact non-ambiguous scalar identities. All unrelated Qs
are free; only separately proved replica equalities are substituted. Actual
source wrong-constant/removed-header-mask mutations and actual mapped wrong-
reset-pin plus wrong-classified-pin controls fail. Receipts list only controls
actually executed; absent S/H groups are explicitly not applicable. All old
controls remain. Reset-aware classification is pair-specific; S→R remains
single-cycle, and the bus-reset producer remains full-rate as reset data.
Standalone EP0 is conditional on both cadence and bus-reset producer contracts,
which the integrated engine discharges. This is sampled digital evidence,
not an inter-edge/physical reset-skew proof.

Diagnostic preparation failures are preserved: formal01's unused cover history
was removed before fminit and was corrected with a reachable release cover;
cert01-03 exposed constant alias and actual GF180 SETN pin handling; cert04
refuted rx_en_q's common-CE hold (it is sample-clock driven); cert05 exposed a
lost primary cadence name, repaired through exact aliases. cert06 was local
proof only before review excluded bus_reset_q from relaxed reset-as-data paths.
cert07 passes the corrected integrated binding. No existing assertion, cap or
assumption was relaxed. Timing now also inventories SETN reset-removal pins.

No packet proof was attempted or restarted; D47 remains exhausted and D50
ineligible. Sampling equivalence and exhaustive applied-exception/per-class
over-budget qualification remain open. Independent review checked the group
composition, reset-as-data exclusion, aliases, controls, enable sizing and
constraint partition. Fresh frozen aggregate and fast CI fail at USB. All ten non-packet cases, their covers/faults and supporting controls pass; packet positives and sampling/exception qualification remain open. Full tier was not run.

## D52 scoped packet attempt, 2026-11-19

Baseline acf8edb090f9ec9cda0c413d3bbbd54da4c6dccf plus receipts' source hashes.
The approved attempt retains the existing depth 48 and 120-second solver cap,
with a 45-minute wall-clock ceiling and at most three distinct rungs. No
unchanged timed-out positive job is restarted. Production buffers are unchanged.

Step 0 reuses preserved measured diagnostics, not new acceptance results:
`python tools/env/run.py run -- python3 scratch/t19_packet_step0_review.py`
and its `--split-stat` run; receipts `build/t19/packet-step0-review-01` and
`build/t19/packet-partition-stat-review-01`.

| Historical measured model | Cells / state bits / RAM bits | Depth 12 / 24 seconds | Control-only cells / bits / RAM |
| --- | --- | --- | --- |
| IN lane | 340 / 261 / 576 | 0.617 / 5.973 | 158 / 81 / 0 |
| OUT lane | 319 / 244 / 576 | 0.466 / 4.621 | 126 / 69 / 0 |

The earlier depth-48 positives timed out; shallow bounded passes are not proofs.
The control partition removes data equalities only in that partition; its
complement retains them, and the union must equal all six original assertions.
Existing real-model covers and faults remain required. Sparse memory requires
its separate actual-word refinement, and all helper invariants stay assertions.

Rungs: independent-reset qualified-read composition; exhaustive assertion
partition; one OUT ownership strengthening motivated by the preserved trace.
The unconditional common-reset memory-age/tag premises cannot establish
independent-reset warmup. The new harness uses production cadence and shared
ResetRelease, with arbitrary independent transport reset. It proves qualified
IN reads and actual OUT head-advance/capture occur after RAM warmup. This local
result does not prove the retained SIE consumption/ACK contract.

D52 results (measured commands on the baseline/hash inventories above):

- `python tools/env/run.py run -- python3 hw/ip/usb/formal/check.py --json build/t19/regmap/usb_regs.json --case buffer_reset --case cadence_reset --case reset_aware --case reset_aware_early --output build/t19/d52-cadence-02`: all proofs, covers and faults pass. The revised local reset harness directly observes the proof-only production OUT capture condition, proves its delayed head-change correspondence, and covers IN and OUT reads after another reset. No default production buffer state or behavior changes.
- `python tools/env/run.py run -- python3 hw/ip/usb/formal/check.py --json build/t19/regmap/usb_regs.json --case cadence_reset --case reset_aware --case reset_aware_early --case out_ownership --output build/t19/d52-formal-01`: OUT strengthened sparse proof TIMEOUT, measured 121.638 seconds including orchestration at the unchanged 120-second solver cap; real-model cover/fault pass. No retry.
- `python tools/env/run.py run -- python3 hw/ip/usb/formal/packet_partition.py --json build/t19/regmap/usb_regs.json --output build/t19/d52-packet-partition-01`: all four partitions TIMEOUT. Measured elapsed seconds: IN control 121.726, IN data 121.186, OUT control 121.133, OUT data 121.136; total runner 507.834 seconds including emission/preparation. Configured depth 48, unbounded ABC PDR, unchanged solver cap. No positive acceptance result.

The third distinct rung exhausts this scoped attempt before its wall-clock
ceiling. The smallest next proposed work is separate proved pointer/occupancy
and service-lifecycle invariants, then data ownership composition; RAM removal
alone did not close even the control partitions. That is unmeasured future
proof engineering, not an assumption or accepted deferral. No unchanged job
is rerun and no buffer restructuring or parameterization occurs.

Independent review corrected initially vacuous reset covers and an inferred
capture witness; the final reset proof has actual observation covers and a
proved witness relation. It also requested build-only output containment and
nonzero exit for unresolved partition results. Those CLI-only safeguards were
added after preserving the solver receipts, without rerunning exhausted jobs.
The historical partition command exited zero while its receipt explicitly
said unresolved; the maintained runner now fails closed. Complete packet/SIE
composition remains unresolved.


D52 frozen confirmation: `python tools/env/run.py run -- python3
hw/ip/usb/check.py --output build/t19/d52-frozen-check-01` passes all eleven
focused cases, covers/faults, byte CDC and reproduced-reference resume
equivalence. Both IN/OUT default production emissions match D51 byte for byte.
No exhausted positive packet proof is rerun. Aggregate and fast CI fail with
the original outstanding obligations retained; full tier is unrun. All frozen
input hashes match before reporting-only edits. Independent reviews clear
certificate-preserving sizing, equivalence/fault extraction, reset warmup and
the assertion partition for an incomplete review checkpoint only.


## D53 measured candidate, 2026-11-19

D53 current checks (same base commit plus exact hashes in receipts):

```sh
python tools/env/run.py run -- python3 tools/sbt.py hw/compile
# success
python tools/env/run.py run -- python3 hw/ip/usb/formal/check.py --json build/t19/regmap/usb_regs.json --case in --case out --case buffer_reset --output build/t19/d53-packet-01
# FAILED USB focused formal: IN/OUT TIMEOUT; reset emitter hit SBT-lock wait cap
python tools/env/run.py run -- python3 scratch/t19_d53_refinement.py
# emit 0, proof 0: actual-RAM refinement and mis-phased/wrong-size controls pass
python tools/env/run.py run -- python3 hw/ip/usb/formal/sie_enable.py --packet-bytes 16 --output build/t19/d53-sie-enable-01
# PASS SIE enable implication; no timing exception applied
python tools/env/run.py run -- python3 scratch/t19_d53_sram_area.py
# PASS pinned SRAM catalog: 28 LEF views, verified archive hashes; area estimate only
python tools/env/run.py run -- python3 hw/ip/usb/check.py --output build/t19/d53-frozen-check-01
# FAILED T19 USB; inspect result.json for every unresolved obligation
python tools/env/run.py run -- python3 tools/ci.py --tier fast --output build/t19/d53-frozen-fast-01
# FAILED T19 USB; inspect result.json for every unresolved obligation
```

The refinement helper runs the reproducible component commands
`python3 tools/sbt.py "runMain deadhorse.usb.EmitUsbMemoryRefinement build/t19/d53-refinement-01/emit"`
and `python3 hw/ip/usb/formal/memory_refinement.py --emit build/t19/d53-refinement-01/emit --packet-bytes 16 --output build/t19/d53-refinement-01/proof`.
The initial `testOnly deadhorse.usb.UsbThroughputSpec` compile failed on a test
method/Boolean name collision; after that local fix the diagnostic simulation
passed its positive rate test and exposed the same replay failure. Frozen
simulation repeats it with the reviewed clock scheduler and recurring tail SOFs.

Frozen USB simulation: 12 passed, 1 failed (all 11 prior tests and the positive
throughput test pass; throttled replay fails). Eleven focused formal cases,
real-buffer covers/faults, byte CDC, resume equivalence, mapping/certificate
controls and actual-RAM refinement pass. The reset-emission infrastructure
failure is recovered by fresh `buffer_reset` proof in the aggregate. No timed-out
positive packet job is retried. Earlier IN/OUT timeout receipts predate the OUT
oracle-width correction and are historical diagnostics, not current proof.

Standalone buffers/resume/register timing passes. EP0 numerically passes but is
qualification-blocked. Engine, wrapper and standalone SIE fail. Both frozen
commands exit 1; fast CI stops at USB, with preceding checks and existing explicitly
unproved deferrals retained. **Full tier: not run.** All source inventories match
before reporting-only edits; repeated timing classes/areas match exactly.
This is an incomplete review checkpoint, not adoption or T19 completion.


Measured by `python tools/env/run.py run -- python3 hw/ip/usb/check.py --output
build/t19/d53-frozen-check-01`, base commit
d45e50f457f3576949b8fdbfd6e1bb69652aaa53 plus frozen source hashes.
Full public MMIO/CDC wrapper, assumed USB 48 MHz and application/AON 12 MHz,
continuous fair polling, seed 5715/5716. Host schedule offers 128 payload bytes
per 1 ms frame per active direction for 10 frames; CRC/stuffing, SOFs, retries,
refill/drain and final transport overhead are included. Unique ACK-committed IN
bytes and OUT bytes actually read/popped through MMIO form the numerator.
These are digital simulation rates under this service contract, not host/board
qualification or a maximum-throughput estimate.

| Traffic | Measured samples | Measured IN bytes | Measured OUT bytes | Measured IN bit/s | Measured OUT bit/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| IN only | 480712 | 1280 | 0 | 1022483.316 | 0.000 |
| OUT only | 480000 | 0 | 1280 | 0.000 | 1024000.000 |
| Simultaneous | 480712 | 1280 | 1280 | 1022483.316 | 1022483.316 |

Each active IN run delivered 80 full 16-byte packets, seven deliberate lost-ACK
retries and one final ZLP; no short IN packets occurred in the positive schedule.
The target is the user-approved 1 Mbit/s, conservatively required in each direction.

The throttled-service negative control **fails on a real protocol defect before
the rate oracle is reached**: DATA1 payload `[126]` replays as `[126,214]` after
another application write and a lost ACK. The exact retry assertion is retained.
Independent review confirms the same visible-tail refresh logic in the 64-byte
D52 baseline: this is an inherited replay-boundary bug, not a size-induced data
corruption claim. A host may discard the longer duplicate then ACK, losing the
added byte when the DUT commits it. No successful rate-negative-control result
or complete packet correctness is claimed.

Step 0 evidence for the changed production 16-byte diagnostic, measured by the
formal command above and `python tools/env/run.py run -- python3 scratch/t19_d53_model_stats.py`
on its preserved prepared models (Yosys `stat`; no solver retry):

| Property | Prepared cells | Sequential bits excluding RAM | RAM bits | Requested depth / last printed PDR frame | Result |
| --- | ---: | ---: | ---: | --- | --- |
| IN original assertions |256|161|192|48 /83|TIMEOUT,122.080 s measured wall time;120 s solver cap|
| OUT original assertions, before oracle-width fix |235|153|192|48 /27|TIMEOUT,121.183 s measured wall time;120 s solver cap|

Measured cover traces have 15/19/23/23 time steps for IN and 11/16/17 for OUT.
These are the existing public-behavior covers, not full/wrap/max-packet covers.
Quarter/half-depth growth sweeps are not rerun: ABC PDR is unbounded, the prior
triage portfolio/lane/sparse/partition budget is exhausted, and no unchanged
timeout retry is justified. Memory is still the dominant state component;
complete packet lifecycle/control remains relevant to the original properties.

No small-model attempt starts. Estimated minimum IN fill spacing at the smallest
supported 8-byte model is 7 intervals×8 sample edges=56 edges after the first RAM
write, excluding startup; full/wrap take longer than the fixed 48 cover bound.
Independent review confirms the parametric source and this lower bound. The
smallest proof-path change would require an explicit cover-budget decision and
separate proved lifecycle/occupancy/service invariants, not more unchanged PDR
time. Fixing the observed replay defect is a prerequisite for full protocol claims.
