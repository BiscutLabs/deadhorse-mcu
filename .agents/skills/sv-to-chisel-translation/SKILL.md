---
name: "sv-to-chisel-translation"
description: "Use when translating existing SystemVerilog (the pinned Ibex reference) into Chisel that must be proved formally equivalent to the original, or when debugging a failed equivalence check on a translated module."
---

# SystemVerilog to Chisel translation that passes equivalence (Deadhorse)

The job is a translation, not a redesign. Success is a formal equivalence
result against the unmodified reference, module by module. Most failures come
from a small set of language differences listed here. Check each one before
running the proof.

Status: first version, written from language semantics. No translation or
equivalence run has happened in this repository yet. Where the T10 harness or
a real run contradicts this file, the run wins: report the difference so the
skill can be corrected.

## Ground rules

1. Change nothing. No restructuring, retiming, state re-encoding, renamed
   signals, merged modules or "cleaner" logic. Write ideas in the design
   notes for a later task.
2. One Chisel module per reference module, same name, same ports, same
   registers.
3. Never edit the reference. If it looks wrong, stop and report.
4. Leaf modules first. A module is done only with its equivalence result.
5. Use the parameter set and defines fixed by the T10 report. Keep
   parameters as Scala constructor arguments; do not hard-code them.

## Names: make the emitted SystemVerilog line up

Equivalence tools match ports and registers by name.

- Module name: `override def desiredName = "ibex_alu"`.
- Ports: declare each port as its own `IO` so no `io_` prefix is emitted.
  `val operand_a_i = IO(Input(UInt(32.W)))`.
- Clock and reset are ordinary named ports. Use `RawModule`:

  ```scala
  class ibex_counter extends RawModule {
    override def desiredName = "ibex_counter"
    val clk_i  = IO(Input(Clock()))
    val rst_ni = IO(Input(Bool()))
    withClockAndReset(clk_i, (!rst_ni).asAsyncReset) {
      // registers here
    }
  }
  ```

- Registers: use the reference's name for the `val` (`val counter_q = ...`).
  Do not wrap registers in helper functions that hide the name; if you must,
  call `.suggestName("counter_q")`.
- Record any name that still differs in `dv/core/module_map.json`.
- Emit with options that keep names and remove randomization. Start from
  `-disable-all-randomization`, `-strip-debug-info`,
  `-preserve-values=named` and lowering option `disallowLocalVariables`;
  confirm against the pinned firtool and record the final set in the report.
- Array ports: check how the pinned firtool emits a `Vec` port against the
  reference's packed or unpacked array, and record the mapping.

## Reset and registers

| Reference | Chisel | Trap |
| --- | --- | --- |
| `always_ff @(posedge clk_i or negedge rst_ni)` with a reset branch | `RegInit(value)` inside the block above | Reset value must match exactly, including width |
| `always_ff @(posedge clk_i)` with no reset | `Reg(UInt(n.W))` | Using `RegInit` here adds a reset and fails equivalence |
| `if (en) q <= d;` | `when(en) { q := d }` or `RegEnable` | Keep the enable; do not fold it into a mux on `d` and back |
| Flop-based register file | `Reg(Vec(n, UInt(32.W)))` | Not `Mem` or `SyncReadMem`; keep register zero as the reference has it |

A module may mix reset and unreset registers. Match each one individually.

## Widths and signs

SystemVerilog widens every operand to the width of the whole expression
context before it computes. Chisel computes at the operand widths. Work out
the reference's context width first, then write it explicitly.

| Reference | Chisel |
| --- | --- |
| `logic [32:0] s = a + b;` (33-bit context) | `a +& b` |
| `logic [31:0] s = a + b;` | `a + b` (truncates to 32) |
| `a + b + cin` into 33 bits | pad all operands to 33 bits first, then `+` |
| `a << sh` into 32 bits | `(a << sh)(31, 0)`; dynamic left shift grows in Chisel |
| `a >> sh` | `a >> sh` on `UInt` |
| `$signed(a) >>> sh` | `(a.asSInt >> sh).asUInt` |
| `$signed(a) < $signed(b)` | `a.asSInt < b.asSInt` |
| `a < b` where either side is unsigned | compare as `UInt`; one unsigned operand makes the whole comparison unsigned |
| `{a, b}`, `{4{x}}` | `Cat(a, b)`, `Fill(4, x)` |
| `{{24{a[7]}}, a[7:0]}` | `Cat(Fill(24, a(7)), a(7, 0))` |
| `a[7:0]`, `a[i]` | `a(7, 0)`, `a(i)` |
| `|a`, `&a`, `^a` | `a.orR`, `a.andR`, `a.xorR` |
| `!a` on a multi-bit value | `a === 0.U` |
| `a && b` on multi-bit values | `a.orR && b.orR` |
| `'0`, `'1` | `0.U(n.W)`, `Fill(n, 1.U)` |
| `x inside {A, B}` | `x === A \|\| x === B` |
| `$clog2(n)` | `log2Ceil(n)` |
| Unsized literal `1` in arithmetic | it is 32 bits wide in the reference; size it to match |

Signed multiplies built as `$signed({sign_bit, operand})` must keep the same
extended width on both sides. Check the product width (sum of operand widths).

## Combinational blocks

- `always_comb` with defaults at the top and later overrides becomes
  `WireDefault(...)` followed by `when` or `switch`. Chisel's last connection
  wins, as in the reference.
- Priority `if / else if` becomes `when / .elsewhen / .otherwise` in the same
  order.
- `unique case` becomes `switch / is`. Keep the default branch's values as
  the `WireDefault`.
- `casez` with wildcards becomes `BitPat`: `when(instr === BitPat("b?????????????????000?????1100011"))`.
  Count the bits.
- Assigning part of a vector (`x[3:0] = ...` in one place, `x[7:4]` in
  another): a Chisel `UInt` cannot be assigned by slice. Build separate
  wires and `Cat` them, or use a `Vec` of `Bool` and `.asUInt`.
- Apparent combinational loops: the reference may read one bit of a vector
  to compute another bit of the same vector. firtool can reject this as a
  loop. Split the vector into separate wires.
- `generate if` becomes a Scala `if`; `generate for` becomes a Scala `for`.
  The emitted names inside generated blocks will differ: record them.

## Types

- Package constants and functions become a Scala `object` with `def`s.
- Enums: the encoding and the width must match. `ChiselEnum` picks the
  minimum width, which may differ from `typedef enum logic [6:0]`. When it
  differs, use plain `UInt` constants of the exact width in an `object`.
- Packed structs become a `Bundle` with fields in the same order. In both
  languages the first field is the most significant when flattened. Add one
  test that flattens the bundle and checks a known bit position, then trust it.
- Packed arrays: element 0 is least significant in both `Vec.asUInt` and the
  reference. Check with the same kind of test.

## Don't-care values, assertions and conditional code

- Where the reference assigns `'x` or `'X`, drive a fixed value in Chisel
  (zero unless the harness says otherwise). Do not use `DontCare`. The
  harness treats a reference `x` as "any value". If a proof fails only where
  the reference is `x`, report it; do not add assumptions to hide it.
- Reference assertion macros (`ASSERT`, `ASSERT_KNOWN` and similar) are not
  behaviour. Do not translate them into logic. They may become Chisel
  assertions, kept out of the equivalence comparison.
- For `ifdef` regions, follow the defines fixed in the T10 report. Do not
  translate regions that are compiled out.
- Clock gating uses the project's gating wrapper, not the reference
  primitive. This is the one intended difference: record it and prove
  equivalence with the gate enables matched (see the T11 brief).

## Working loop for one module

1. Read the reference module and list its ports, registers (with reset or
   not), parameters and submodules.
2. Translate. Keep the reference's statement order where it helps review.
3. Before any proof, compare the lists from step 1 against the emitted
   SystemVerilog: same module name, ports, widths, register names and count.
4. Run the module's equivalence check from the T10 harness.
5. Substitute the emitted module into the reference hierarchy and run the
   parent's lockstep or simulation test.
6. Record the result in the per-module table: proved, bounded with depth and
   reason, or excluded with reason.

## When equivalence fails

Read the counterexample before changing code.

1. Find the first output or register that differs, and the cycle.
2. Trace back to the smallest expression that differs. Evaluate both sides
   by hand with the counterexample's input values.
3. Check, in this order: width or carry, signed versus unsigned, shift
   growth, a register that gained or lost its reset, a reset value, an enum
   encoding, case priority, a default that was dropped, a compiled-out
   region.
4. Fix the translation, not the proof. Never add an assumption, exclude a
   signal or lower the depth to get a pass.
5. If state cannot be matched by name, fix the names before trying a deeper
   sequential proof.

## Stop and ask

- The reference seems to contain a bug.
- A module passes only with an assumption the reference's own constraints do
  not contain.
- A construct has no faithful Chisel form without changing structure.
- The pinned firtool cannot emit matching names or ports for a module.
