# 12 Formal verification

Formal proof is the first choice for verifying Deadhorse's control logic,
with simulation covering what proof cannot reach. The wider verification
strategy (simulation layers, FPGA, signoff gates) is in
[08-physical-verification.md](08-physical-verification.md).

Nothing in this document has been run by this project yet. The tool chain
is established in the build task before any block relies on it.

## Policy

1. **Every new block ships with properties.** A block's `formal/` directory
   holds its properties and proof scripts, or its README says in one line
   why formal does not apply.
2. **Prove, do not just bound, where the block is small enough.** Each
   property is recorded as *proved* (unbounded: induction or an unbounded
   engine), *bounded* (holds to a stated depth) or *covered* (a witness
   exists). A bounded result is never reported as a proof. A result
   obtained with arithmetic replaced by a simpler function is recorded as
   *arithmetic abstracted* beside its kind, and never as a plain result.
3. **Assumptions are part of the proof.** Every `assume` is listed in the
   block README with its justification, and wherever a block's assumption
   is another block's guarantee, that guarantee is itself a checked
   property.
4. **No vacuous proofs.** Each proof has cover statements showing the
   interesting states are reachable under its assumptions.
5. **A proof that cannot fail proves nothing.** Each proof has one negative
   control: a deliberate bug in the design that the proof must catch.
6. **Proofs run in CI** with a time budget per block, and results go in a
   proof ledger under `docs/ledger/`: property, kind, engine, depth, time.
7. **Never weaken a property to make it pass.** Narrowing a property or
   adding an assumption needs the same review as changing a requirement.

## Tools

| Purpose | Tool | Notes |
| --- | --- | --- |
| Properties in the design language | Chisel `assert`, `assume`, `cover` and its LTL library (`AssertProperty`) | Properties live beside the RTL they describe |
| Model checking Chisel blocks | Chisel's BTOR2 emission (`ChiselStage.emitBtor2`, firtool `--btor2`) with a BTOR2 model checker | The native route for Chisel; bounded checking is certain, unbounded depends on the checker |
| Model checking emitted or vendored SystemVerilog | SymbiYosys with its bounded, induction and PDR engines | Needed for vendored blocks and as a second engine |
| Processor correctness | riscv-formal, through the RVFI trace port | Both Chisel cores need verified RVFI. The performance core is also proved equivalent to the pinned Ibex reference before F is added (T11) |
| Equivalence | Yosys-based equivalence checking | RTL against synthesized netlist, before and after scan insertion, and against the final netlist |

### Multiplication and division (D44)

Bit-level solvers cannot prove a full-width product equal to a multiplier
built from partial products; T10 measured a timeout at 600 and at 1,800
seconds with no counterexample. For multiply, and for divide if it shows the
same behaviour, the instruction check is split: an integration check with
the arithmetic abstracted on both sides (riscv-formal ALTOPS), plus a
separate arithmetic argument (an algebraic identity proved over integers,
and seeded simulation with injected faults). Module equivalence between the
Ibex reference and the Chisel conversion matches multiply operators
structurally and needs no arithmetic proof. The unabstracted end-to-end
check is kept as an on-demand diagnostic recorded as unresolved. Details are
in [tasks/T10-ibex-reference.md](tasks/T10-ibex-reference.md). The same
approach applies to the FPU's multiplier and divider in T12.

Which checker gives unbounded proofs on which block is not known until the
tools are run on real blocks. The proof ledger records what was achieved.

## What gets proved

### Full proofs expected (small, control-dominated)

| Block | Properties |
| --- | --- |
| Clock-domain crossing FIFO | No overflow or underflow; every word written is read exactly once, in order, unchanged (symbolic data tracking); pointers change one bit at a time across the boundary; correct behaviour when either side resets |
| Reset synchronizers | Asynchronous assert, synchronous release, no release before the hold time |
| Domain bridge | Exactly one response per accepted request; address, data and byte enables unchanged; a request toward a stopped clock always wakes it and completes (no lost wake); reset of either side cancels with an error on the surviving side; no duplicate |
| Mailbox | Words delivered once, in order, unchanged; overflow is flagged, never silent; non-empty always raises interrupt and wake |
| Gateway protocol | Exactly one response per host request; malformed or reserved requests rejected without state change; same ownership and memory checks as other masters |
| Generated register blocks | Properties generated from the register description itself: read returns last write for `rw`; software cannot change `ro`; `w1c` clears only written bits and hardware set wins; unmapped and misaligned access returns an error and changes nothing; reset values |
| DMA and ownership | Exclusive peripheral owner; unauthorized transfers have no effects; bounded bursts; ownership handover drains/cancels pending work; memory boundaries enforced |
| Local bus | At most one outstanding transaction; every request answered; decode is exclusive and complete; no starvation between the instruction and data ports |
| Interrupt controllers | A pending enabled interrupt is eventually presented; clear cannot lose a simultaneous set |
| Watchdogs | An unserviced watchdog always resets; software cannot disable or lengthen it once started; window violations reset |
| Power and clock controller | No lost wake-up: a wake that arrives at any point of the sleep sequence results in the main clock running; the fast clock is never stopped with a transaction or actuator frame outstanding; deep sleep is refused while the actuator block is armed |
| Boot and programming lock | The lock clears only on power-on reset or brownout; an unvalidated image is never started; an interrupted update leaves a bootable image |
| Actuator block | From any state, a failsafe cause puts failsafe values on the pins within the specified per-channel fault bound, with the performance bus held in reset and clock/supply valid; publication is atomic and each channel applies at its own frame boundary; no torn values; timeout and approved recovery policy are enforced; the DShot frame equals the specification's function of throttle and telemetry bit |
| QSPI controller arbitration | An execute-in-place read never waits longer than one page transfer; boot and logging chip selects are never active together |

### Bounded proofs and covers (larger or protocol-timed)

| Block | Approach |
| --- | --- |
| UART, SPI, I2C bit engines | Bounded proofs of frame shape and bit timing in clock cycles; covers for every frame type |
| Lite core | riscv-formal instruction, register and program-counter checks, plus interrupt entry and return |
| Performance core | New proofs for the Chisel rewrite; RVFI integer checks plus independent full-F reference tests/properties, including flags and rounding; upstream proof claims are not inherited |
| SoC connectivity | Each pad reaches its peripheral under every pin-mux setting; every signal that crosses a clock domain passes through the crossing block (structural) |
| Reset and unknown values | From reset, no control signal depends on an uninitialised register |

### Equivalence

- Chisel-emitted RTL against the synthesized netlist.
- Netlist before and after scan insertion, in functional mode.
- Final post-layout netlist against the synthesized netlist.

## What formal does not cover here

Stated so nobody assumes otherwise: analog behaviour and oscillator
start-up; static timing; glitch-freedom of clock gates and the clock mux at
the cell level; metastability (the crossing block has a calculated MTBF, not
a proof); whole-chip behaviour with firmware, such as a complete boot or a
flight; vendored blocks' internals beyond what upstream proved. Simulation,
static checks and signoff cover these.

## Order of work

1. **Tool chain smoke test,** as part of the Chisel build task: one trivial
   module with one true property (proved), one false property (caught) and
   one cover, through both the BTOR2 route and SymbiYosys.
2. **The crossing FIFO first.** It is small, it is the block most likely to
   fail in silicon, and it sets the pattern for the proof ledger.
3. **Generated register-block properties,** inside the register-map
   generator task, so every later block gets them for free.
4. **The domain bridge and mailbox,** in T14, building on the crossing FIFO
   proof.
5. **Each remaining block with its RTL,** never after.

## Gate conditions added

- **G1:** the smoke test passes on both routes; the crossing FIFO is proved.
- **G2:** every block in "Full proofs expected" has its proof in CI, or a
  recorded reason it is bounded instead; riscv-formal passes on both cores;
  no unreviewed assumption.
- **G3:** all three equivalence checks pass on the final netlist.
