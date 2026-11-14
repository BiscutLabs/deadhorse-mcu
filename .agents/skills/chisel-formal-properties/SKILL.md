---
name: "chisel-formal-properties"
description: "Use when adding, running or reviewing formal properties for a Deadhorse MCU block in Chisel: choosing properties, proving versus bounding, assumptions, covers and negative controls."
---

# Formal properties for Chisel blocks (Deadhorse)

Formal proof is the first choice for Deadhorse's control logic. The policy and
the per-block property list are in `docs/plan/12-formal-verification.md`; read
that and the task brief first. This skill is about doing it honestly: the
common failures are proofs that pass because they are vacuous or
over-constrained, and bounded results reported as proofs.

## The method

1. **Start from the specification, not the RTL.** List what a user of the
   block may rely on. Each item becomes a property. If you derive properties
   by reading the implementation, you will prove the bugs correct.
2. **Write properties beside the RTL** using Chisel `assert`, `assume`,
   `cover` and the LTL library (`AssertProperty`) for sequences.
3. **Run each property and classify the result:**
   - *proved*: unbounded (induction or an unbounded engine);
   - *bounded*: holds to depth N, with N stated;
   - *covered*: a witness trace exists.
   Never write "proved" for a bounded result.
4. **Add covers** showing the interesting states are reachable under your
   assumptions. A proof with no reachable interesting state is vacuous.
5. **Add one negative control per proof:** plant a specific bug in the design
   and confirm the proof fails. Remove the bug. Record what you planted.
6. **List every `assume`** in the block README with its justification. Where
   it is another block's guarantee, check that the other block asserts it.
7. **Record the result** in the proof ledger under `docs/ledger/`: property,
   kind, engine, depth, run time, commit.

## Choosing properties

| Block kind | Properties that find real bugs |
| --- | --- |
| FIFO, queue, crossing | No overflow or underflow; every accepted item leaves exactly once, in order, unchanged; reset on either side is safe |
| Handshake stage | `valid` stays asserted with stable data until `ready`; no data lost or duplicated; no combinational `ready` to `valid` loop |
| Arbiter | At most one grant at a time. Every requester is eventually granted under fair acceptance. |
| Register block | Read returns the last write for read-write fields; software cannot change read-only fields; write-one-to-clear clears only written bits; unmapped access errors and changes nothing; reset values |
| Bus | At most one outstanding transaction; exactly one response per request |
| State machine | Only legal states are reachable; every state has an exit; safety outputs hold in each state |
| Watchdog, lock, failsafe | The protective action always happens; software cannot disable it; it is left only by the stated condition |
| Sleep and wake control | A wake arriving at any step of the sleep sequence results in a running clock; the clock is never stopped with work outstanding |

### Data integrity without state explosion

To prove data passes through unchanged, do not track all data. Use a
**symbolic tracked item**: let the solver pick one arbitrary value and one
arbitrary position, and assert that this one item comes out once, in order,
unchanged. Because the choice is arbitrary, the proof covers all items.

### Liveness

"Eventually" properties need fairness assumptions (the receiver eventually
accepts). State them explicitly. If the engine cannot do liveness, prove a
bounded response time instead and say so.

## Getting an unbounded proof

- Try induction first. When it fails on an unreachable state, add a
  **strengthening invariant** as an `assert` (never an `assume`) that rules
  that state out, and prove the invariant too.
- Keep blocks small and prove them separately. Replace a proved neighbour
  with its asserted guarantees.
- Shrink widths and depths with parameters for the proof, only if the logic
  does not depend on the size. State the sizes proved.
- If only a bounded result is reachable, choose the depth from the design
  (longer than the deepest queue plus the longest state-machine path), state
  it, and back it with simulation.

## Warning signs that a proof is wrong

- It passes instantly on a non-trivial block.
- Covers are unreachable, or you did not write any.
- An `assume` mentions an internal signal or an output of the block.
- An `assume` was added to make a failing assertion pass.
- The property restates the RTL (`out === the same expression`).
- The negative control does not fail.

## Rules

- **Never weaken a property or add an assumption to get a pass.** Narrowing
  a property needs the same approval as changing a requirement. Report the
  counterexample instead.
- **A counterexample is a result.** Decide whether the design, the property
  or an assumption is wrong, and say which in your report.
- **Do not delete or skip a failing proof.**

## Tools

| Route | Use for |
| --- | --- |
| Chisel BTOR2 emission (`ChiselStage.emitBtor2`, firtool `--btor2`) with a BTOR2 model checker | Chisel blocks |
| SymbiYosys on emitted or vendored SystemVerilog | Vendored blocks, and as a second engine |
| riscv-formal through the RVFI port | The two processor cores |
| Yosys-based equivalence checking | RTL against netlists |

Use two routes on blocks listed for a full proof when you can.

## What formal does not cover

Analog behaviour, static timing, glitch-freedom of clock gates at the cell
level, metastability, and whole-chip behaviour with firmware. Do not claim
them. Simulation and signoff cover those.

## Report

For each property: its statement in words, kind (proved, bounded to N,
covered), engine, run time, the assumptions it relies on, and the negative
control used. List anything you could not prove and why.

## Status of this skill

The formal tool chain had not been run in this project when this was
written. The method is standard practice; the exact Chisel calls and command
lines must be confirmed by the tool chain smoke test before relying on them.