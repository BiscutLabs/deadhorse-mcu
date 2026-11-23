# T32 two-hart debug contract

Implementation is provisional: the expanded production OpenOCD
aggregate, targeted core/debug regressions, full-DM reset tests and TAP extraction
equivalence pass independent review where recorded. The approved area review
resolved the area-only stop. D80 defers the remaining reset-epoch read-data
assertion, which remains unproved. The 2026-11-23 timing follow-up reproduces
65.141479 ns against the unchanged 66.666667 ns budget with all-state mapped
equivalence. Frozen timing-fast01 passes all 34 active CI commands with twelve
inherited unproved deferrals; the separate T32 proof is still deferred, and the
full tier is unrun. Rejected mapping diagnostics remain
recorded. Production-bound reset-halt/loader proofs, covers and
fault controls pass in ownership06. Current local/transport proof
bindings and the maintained area replay are independently reviewed; the USB
acceptance-input refresh passes unchanged collectors. Measured negative removal
and core-clock pulse diagnostics remain T33/T38 physical-flow obligations. See
[T32 report](../../../docs/plan/tasks/reports/T32.md) for exact evidence and limits.
The approved SBA-routing simplification is independently reviewed and retained:
fresh mapping measures 104 fewer flip-flops. The subsequent reviewed physical
observer boundary and balanced reset-buffer mapping give estimated core use
12.855509285 mm2 against the unchanged 12.92 mm2 ceiling. Commands and
the distinction between mapped measurements and budget estimates are in the report.

One PULP riscv-dbg DM, two harts (lite0, performance1), unlocked D41. Main
system clock services the DM; TAP uses external TCK. No extra production
profile. Integration must preserve ordinary boot/loader ownership and resets.

## Adoption

Pinned commit 643607e19df3435cfd77cc56143e2637f5900a6e; common_cells fifo_v3
b5ec8905ed7828655155b0ae971023adf793c600; tech_cells_generic63da15065d2270788634562bb2240514a70f76cc.
NrHarts2, BusWidth32, MaxRegisterAccessWidth32; unchanged eight-word program
buffer, two data words, both harts selectable. Preserve SHL0.51 and Apache/SiFive
notices. Original dmi_cdc is excluded from the production file list. A reviewed interface
patch exposes the TCK handshake for the shared Chisel CDC adapter. The lock-file
patch also normalizes dm_mem reset branches and adds independent hart reset
status and command observation, as specified below. Original failed frontend
evidence is retained under build/t32/.
Standalone patch-audit maps105758.1504um2 (measured command/receipt in
build/t32/vendor-audit-patched); this excludes transport/hooks and is not fit.
OpenOCD0.12.0 commit9ea7f3d647c8ecf6b0f1424002dfc3f4504a162c, remote-bitbang,
internal pinned JimTcl, no hardware USB adapter required. Tool lock/build first.

## Debug window and transaction paths

Bind debug_mem at0x00010000, size0x1000, immediately above boot ROM and
disjoint from XIP. Generate from soc.yaml. Halt entry0x10800, exception0x10810
follow the pinned PULP ROM (not the core's historical exception+8 default).
Window includes DM ROM, flags, generated abstract instructions/program buffer,
data and handshake writes. CPU instruction fetch and data accesses both route.
Perf local-memory debug transactions use a retained native request/response slot
like XIP, with existing client-reset epoch suppression and drain behavior.
Lite accesses this main-domain window via a dedicated leaf instance of the
shared BusBridge and DirectionPermit. The ordinary AON/main bridge remains
unchanged; the leaf avoids extending either fabric beyond its target capacity.
Registered DM memory arbitration accepts one complete request at a time; wrapper
returns exactly one registered response following the DM's registered data.
Access is restricted to the two hart origins; SBA cannot forge hart handshake
writes. No normal firmware window is moved or shrunk.

SBA is a real master tagged origin2, never a spoofed CPU owner. Its adapter
captures address/data/mask/operation, owns the accepted beat through completion,
registers grants and responses and returns bus errors without retry. Eight- and
sixteen-bit operations normalize the word address, preserving upstream lane
mask/data shift; invalid alignment/size errors remain the DM's standard errors.
Performance SRAM uses an arbitrated DMA/debug native-memory ingress, preserving
DMA origin1 and its SRAM-only restriction. Boot-ROM reads may use the same
explicitly checked debug native path; ROM writes fail. Retained SRAM uses a real
main-fabric debug master through the existing bridge. Other unimplemented or
forbidden SBA windows error; no peripheral-owner bypass is added.
The area-reduction experiment captures retained/native destination alongside
the SBA payload and connects directly to the existing downstream fabrics. It
removes only the intermediate SBA routing packet/reply registers; both fabric
arbiters, timeouts, poisoning and the POR-owned cancellation/quarantine remain.
The selector holds until the reply; unrelated responses cannot select a new
destination. No shared CDC storage or lite/performance request stage is removed.
Retained debug writes have a distinct write enable/permission check; ordinary
bus program-write and frozen-loader checks remain. Debug program writes require
lite in debug or not started, and no loader programming in progress. A JTAG
halt never changes the meaning of the loader's notStarted ownership signal.

## Hart semantics

Perf uses existing debug_req/debug mode/DCSR/DPC/DSCRATCH/DRET/single-step;
expose current debug mode as a narrow functional hook, not delayed RVFI. Default
vector parameters stay unchanged for existing standalone reference fixtures;
production overrides only the new generated DM addresses.
Lite adds the standard minimal execution-debug subset: precise debug request at
an instruction boundary (phase boundary AND operation Fetch), DCSR/DPC and two
scratch CSRs, DRET, debug EBREAK re-entry and debug exception vector. x0 remains
zero, x1..15 retained; nonexistent x16..31 and unsupported instructions/CSRs
trap within debug and report an abstract-command exception. No lite single-step
claim is made. Normal machine interrupts defer during debug; on resume their
pending levels remain effective. Debug preserves application PC/GPR/machine
CSRs except explicitly requested debugger writes. Cycle counters retain their
specified behavior; no watchdog/PWM/DMA freeze is introduced.
Both harts advertise two scratch registers without direct scratch-data mapping:
the debug data window cannot be encoded in hartinfo's signed dataaddr field.
Existing LiteCore.halted/notStarted is distinct from debugMode/debug status.
Debug entry never fabricates a loader START. An in-flight load/store completes
before halt; the application PC saved is the next unexecuted instruction.

## Reset, debug-only execution and wake

POR resets TAP/DM/transport; warm, watchdog, target service/core resets do not
reset DM state. ndmreset affects ordinary main/AON/USB state via existing reset
cohorts, never the DM itself. Shared ResetRelease provides async assert and
sync release. ndmreset acknowledgment follows actual ordinary reset assertion.
Hart unavailable remains asserted until its reset and transaction epoch permit
safe execution; pending selected halt request survives reset.

To permit halt-on-reset without manufacturing normal boot release, use a
separate selected-hart debug execution grant. Capture it outside target reset;
normal BootControl.released/boot_seen and loader validation/lock are unchanged.
All real resets and memory epoch fences dominate. For performance debug entry,
keep fetch disabled until actual debug mode is entered, then allow the DM ROM;
prove no application instruction retires first. Grant persists through parked
commands and explicit resume; dropping haltreq must neither reset the hart nor
start normal boot. Explicit debugger resume can execute the debugger's DPC as
D41-authorized debug execution. Teardown of dmactive after a debug-only release
must drain its client and return it to ordinary boot hold unless normal boot
release has since occurred; it cannot replay a stale resume. Lite preserves
notStarted while executing the debug park; loader admission is separately
inhibited during that session to prevent simultaneous ownership.

TAP TestLogicReset/dmihardreset flush DMI request/response epochs through shared
FIFO reset release and clear the DM response FIFO. Already accepted SBA side
effects drain exactly once; never replay a write. DM deactivation cannot erase
accepted adapter work. Target reset before response produces one cancellation
error. An already committed write may drain once after cancellation; reset is
not rollback. Local quiet/credit signals do not establish that all remote work
has disappeared. End-to-end stale-response exclusion remains a composed proof
obligation, including a fabric capture whose registered grant follows request
withdrawal. Drain bookkeeping counts that committed registered grant.

TCK-domain pending request is a retained level synchronized into ungated AON;
it starts main even when main is stopped. DM active/session/SBA work holds main
and AON demand through the existing collector. T33 receives explicit demand and
ndmreset interfaces; T32 tests external digital clock stop/restart, not analog
oscillator behavior. Supported initial TCK maximum is assumed100kHz when main
runs at8/9MHz; AON may be32kHz or active1MHz. Shared FIFOs provide arbitrary phase
safety; debugger retry handles busy. Validate worst ratios in simulation.
No TRST pad added: POR plus TAP's standard five-TMS-high sequence resets TAP.
TDO uses the adopted falling-edge register; testmode tied low until T37.

## Acceptance

Actual remote-bitbang drives production JTAG pins through pinned OpenOCD. Test
both hart enumeration, independent halt/resume/GPR/PC accesses, SRAM SBA, reset
halt and exact one-instruction perf step. Directed and randomized tests cover
bus backpressure/errors, invalid/unsupported commands, reset during request,
stopped clocks/wake and actual missing-halt fault. No host backdoor substitutes
for JTAG operations; any initial fixture firmware loading is explicit.
Prove transport exactly-once/stability/reset cancellation and selected-hart
isolation, with duplicate/stale/wrong-hart faults, real covers and named clock-
progress assumptions only for liveness. Prove no application execution before
reset-halt entry and no loader permission gained by ordinary debug halt.
Retain all affected core/reference tests and run synthesis/timing per domain,
area-budget replacement, frozen fast tier and independent implementation review.
Independent contract review accepted revision 2 on 2026-11-22. Implementation
and acceptance checks remain in progress; contract review is not a test pass.

## Review resolutions, revision 2

- Debug-only teardown: performance immediately reasserts its existing client
  reset when DM deactivates; the service-side native/MMIO slots drain retained
  accepted work and epochReady stays low until safe. Ordinary bootReleased=true
  harts do not reset. Lite debug-only teardown first requests an instruction-
  boundary stop, stops new offers, waits for LiteBusAdapter idle, then resets
  only the hart/adapter client state; the AON fabric, retained memory and loader
  stay alive. Normal-started lite does not reset on deactivation. No automatic
  resume on deactivation; an ordinarily started parked hart stays parked.
- Lite debug ownership acquisition waits for loaderBusy=false and retained
  memory idle. Existing loader.halted admission is masked only after acquisition;
  an already accepted loader write completes first. A continuously busy loader
  can delay debug acquisition; no unconditional progress proof assumes otherwise.
  Debug-only resume retains notStarted for ordinary boot ownership, but debug
  ownership continues to inhibit loader admission until explicit session teardown.
  An existing normally started hart keeps notStarted=false throughout debug.
- DM memory handshake accesses require actual issuing hart debug mode and
  selected debug-transaction epoch. HALTED/RESUMING written hart IDs must match
  trusted origin. GOING/EXCEPTION and abstract-data/program execution writes
  must match the command's captured hart; the contract uses exported status
  from the adopted DM through a reviewed observation-only patch, not guessed
  host timing. Wrong-hart requests return error without DM state mutation.
- hasresethaltreq remains0. Halt-on-reset uses held haltreq and the per-hart
  debug-entry pending latch; OpenOCD reset-halt sequence is tested. No optional
  set/clrresethaltreq or individual hartreset support is advertised.
- Add a narrowly reviewed independent-reset patch to DM: per-hart reset input
  clears that hart's halted/resume-ack/pending-resume state, sets its havereset,
  and aborts only an active abstract command belonging to that hart with the
  standard halt/resume error. Halt request/session state survives. Defaults
  preserve unmodified upstream behavior when this extension is disabled, which
  must be equivalence checked. Asserting unavailable alone is insufficient
  because stale halted status could return after release. Reset wins over same-
  cycle hart acknowledgement. Shared reset-release/retained observation detects
  short target resets even with main stopped; stale DM-memory traffic is cancelled.
- DTM uses an interface-only patch moving its dmi_cdc instantiation outside the
  vendor module: unchanged TAP/DTM FSM drives the same request/response handshake
  at TCK; Chisel instantiates shared CdcFifo/ResetRelease directly. Avoid an opaque
  foreign CDC or separately emitted duplicate shared modules. Register the TCK
  clear before using it to flush the paired FIFOs; core-up qualification holds
  response-FIFO clear until the new epoch is live. Verify DTM behavior and phase
  resets against the original with actual scan transactions.

Review obligations: debug ownership acquisition is atomic against same-edge
loader command/START admission; previously offered writes drain. Per-hart reset
wins over simultaneous command acceptance/acknowledgement without cancelling
the other hart command. Both races require directed negative/regression cases.
