// Copyright lowRISC contributors.
// Copyright 2018 ETH Zurich and University of Bologna, see also upstream CREDITS.md.
// Licensed under the Apache License, Version 2.0; SPDX-License-Identifier: Apache-2.0
// Translation of rtl/ibex_alu.sv and alu_op_e in rtl/ibex_pkg.sv,
// Ibex 38c070939183cc10940b66c8e9e04eeca6b65470, pinned RV32BNone configuration.
package deadhorse.perf_core

import chisel3._
import chisel3.util.{Cat, Reverse, Mux1H, addAttribute}

object IbexAluOp {
  // Exact declaration order of the explicitly 7-bit upstream enum.
  private val names = Seq(
    "ADD", "SUB", "XOR", "OR", "AND", "XNOR", "ORN", "ANDN",
    "SRA", "SRL", "SLL", "SRO", "SLO", "ROR", "ROL", "GREV", "GORC",
    "SHFL", "UNSHFL", "XPERM_N", "XPERM_B", "XPERM_H",
    "SH1ADD", "SH2ADD", "SH3ADD", "LT", "LTU", "GE", "GEU", "EQ", "NE",
    "MIN", "MINU", "MAX", "MAXU", "PACK", "PACKU", "PACKH", "SEXTB", "SEXTH",
    "CLZ", "CTZ", "CPOP", "SLT", "SLTU", "CMOV", "CMIX", "FSL", "FSR",
    "BSET", "BCLR", "BINV", "BEXT", "BCOMPRESS", "BDECOMPRESS", "BFP",
    "CLMUL", "CLMULR", "CLMULH", "CRC32_B", "CRC32C_B", "CRC32_H",
    "CRC32C_H", "CRC32_W", "CRC32C_W")
  private val values = names.zipWithIndex.toMap
  def apply(name: String): UInt = values(name).U(7.W)
}

class IbexAlu(val RV32B: Int = 0, val normalResultOnly: Boolean = false) extends RawModule {
  require(RV32B == 0, "T11 implements the pinned RV32BNone configuration")
  override def desiredName = "ibex_alu"
  val operator_i = IO(Input(UInt(7.W)))
  val operand_a_i = IO(Input(UInt(32.W)))
  val operand_b_i = IO(Input(UInt(32.W)))
  val instr_first_cycle_i = IO(Input(Bool()))
  val multdiv_operand_a_i = IO(Input(UInt(33.W)))
  val multdiv_operand_b_i = IO(Input(UInt(33.W)))
  val multdiv_sel_i = IO(Input(Bool()))
  // Packed representation of the upstream two-word unpacked ports. All bits
  // remain present; RV32BNone ties both output words to zero.
  val imd_val_q_i = IO(Input(UInt(64.W)))
  val imd_val_d_o = IO(Output(UInt(64.W)))
  val imd_val_we_o = IO(Output(UInt(2.W)))
  val adder_result_o = IO(Output(UInt(32.W)))
  val adder_result_ext_o = IO(Output(UInt(34.W)))
  val result_o = IO(Output(UInt(32.W)))
  val comparison_result_o = IO(Output(Bool()))
  val is_equal_result_o = IO(Output(Bool()))

  private def op(names: String*): Bool =
    names.map(name => operator_i === IbexAluOp(name)).reduce(_ || _)

  // Approved timing repair: parallel local sums and a balanced group carry
  // tree. Keep the combinational group boundaries through area-driven mapping.
  private def fastAdd(a: UInt, b: UInt, width: Int, carryIn: Bool = false.B): UInt = {
    def keep(value: UInt): UInt = {
      val wire = WireDefault(value)
      addAttribute(wire, "keep = 1")
      wire
    }
    val x = a.pad(width)
    val y = b.pad(width)
    val groups = (0 until width by 4).map { low =>
      val high = math.min(low + 3, width - 1)
      val n = high - low + 1
      val sum = keep(x(high, low) +& y(high, low))
      val propagate = keep((x(high, low) ^ y(high, low)).andR.asUInt).asBool
      (sum, propagate, n)
    }
    def combine(high: (Bool, Bool), low: (Bool, Bool)): (Bool, Bool) = {
      val g = keep((high._1 || (high._2 && low._1)).asUInt).asBool
      val p = keep((high._2 && low._2).asUInt).asBool
      (g, p)
    }
    def prefix(parts: Seq[(Bool, Bool)]): (Bool, Bool) = {
      if (parts.size == 1) parts.head
      else {
        val split = parts.size / 2
        combine(prefix(parts.drop(split)), prefix(parts.take(split)))
      }
    }
    val gp = groups.map { case (sum, p, n) => (sum(n), p) }
    val sums = groups.zipWithIndex.map { case ((sum, _, n), i) =>
      val incremented = keep(sum(n - 1, 0) + 1.U(n.W))
      val carry = if (i == 0) carryIn else {
        val (g, p) = prefix(gp.take(i))
        g || (p && carryIn)
      }
      Mux(carry, incremented, sum(n - 1, 0))
    }
    Cat(sums.reverse)
  }

  // For a zero modular sum, carry into a slice is exactly carryIn OR any
  // lower bit of a. Check each short slice with that candidate carry in
  // parallel; their conjunction is equivalent to the full zero-sum test.
  private def zeroSum(a: UInt, b: UInt, carryIn: Bool = false.B): Bool = {
    val nonzero = (0 until 32 by 4).map { low =>
      val wire = WireDefault(a(low + 3, low).orR)
      addAttribute(wire, "keep = 1")
      wire
    }
    val matches = (0 until 32 by 4).map { low =>
      val x = a(low + 3, low)
      val y = b(low + 3, low)
      val carry = if (low == 0) carryIn else carryIn || Cat(nonzero.take(low / 4)).orR
      val hit = WireDefault(Mux(carry, x === ~y, (x + y) === 0.U))
      addAttribute(hit, "keep = 1")
      hit
    }
    Cat(matches).andR
  }

  val operand_a_rev = Reverse(operand_a_i)
  val operand_b_neg = ~Cat(operand_b_i, false.B)
  val adder_op_b_negate = op("SUB", "EQ", "NE", "GE", "GEU", "LT", "LTU",
    "SLT", "SLTU", "MIN", "MINU", "MAX", "MAXU")
  val adder_in_a = Mux(multdiv_sel_i, multdiv_operand_a_i, Cat(operand_a_i, true.B))
  val adder_in_b = Mux(multdiv_sel_i, multdiv_operand_b_i,
    Mux(adder_op_b_negate, operand_b_neg, Cat(operand_b_i, false.B)))
  val sum_add = fastAdd(operand_a_i, operand_b_i, 33)
  val sum_sub = fastAdd(operand_a_i, ~operand_b_i, 33, true.B)
  val sum_multdiv = fastAdd(multdiv_operand_a_i, multdiv_operand_b_i, 34)
  adder_result_ext_o := Mux(multdiv_sel_i, sum_multdiv,
    Mux(adder_op_b_negate, Cat(sum_sub, false.B), Cat(sum_add, true.B)))
  val adder_result = adder_result_ext_o(32, 1)
  adder_result_o := adder_result

  val cmp_signed = op("GE", "LT", "SLT", "MIN", "MAX")
  val is_equal = Mux(multdiv_sel_i,
    zeroSum(multdiv_operand_a_i(32, 1), multdiv_operand_b_i(32, 1),
      multdiv_operand_a_i(0) && multdiv_operand_b_i(0)),
    Mux(adder_op_b_negate, operand_a_i === operand_b_i, zeroSum(operand_a_i, operand_b_i)))
  val is_greater_equal = Mux(operand_a_i(31) === operand_b_i(31),
    !adder_result(31), operand_a_i(31) ^ cmp_signed)
  val lessComparison = op("LT", "LTU", "MIN", "MINU", "SLT", "SLTU")
  val orderedComparison = op("GE", "GEU", "MAX", "MAXU") || lessComparison
  val cmp_result = Mux(orderedComparison, is_greater_equal ^ lessComparison, is_equal ^ op("NE"))
  comparison_result_o := cmp_result
  is_equal_result_o := is_equal
  // EX never selects result_o during mult/div. This parent-proved variant
  // removes that unobservable dependency before the result mux, while adder
  // and comparison ports retain their complete original behavior.
  val result_adder = if (normalResultOnly) Mux(adder_op_b_negate, sum_sub(31,0), sum_add(31,0)) else adder_result
  val result_cmp = if (normalResultOnly) {
    val equal = Mux(adder_op_b_negate, operand_a_i === operand_b_i, zeroSum(operand_a_i, operand_b_i))
    val ge = Mux(operand_a_i(31) === operand_b_i(31), !result_adder(31), operand_a_i(31) ^ cmp_signed)
    Mux(orderedComparison, ge ^ lessComparison, equal ^ op("NE"))
  } else cmp_result

  val shift_amt_compl = 32.U(6.W) - operand_b_i(4, 0).pad(6)
  val shift_amt = Mux(instr_first_cycle_i, operand_b_i(4, 0), shift_amt_compl(4, 0))
  val shift_left = op("SLL")
  val shift_arith = op("SRA")
  val amount = operand_b_i(4, 0)
  val amountZero = amount === 0.U
  val leftDirect = WireDefault((operand_a_i << amount)(31, 0))
  val rightDirect = WireDefault(operand_a_i >> amount)
  val signedDirect = WireDefault((operand_a_i.asSInt >> amount).asUInt)
  val leftComplement = WireDefault((Cat(operand_a_i, 0.U(32.W)) >> amount)(31, 0))
  val rightComplement = WireDefault((operand_a_i.pad(64) << amount)(63, 32))
  val signedComplement = WireDefault((operand_a_i.asSInt.pad(64).asUInt << amount)(63, 32))
  Seq(leftDirect, rightDirect, signedDirect, leftComplement, rightComplement, signedComplement)
    .foreach(wire => addAttribute(wire, "keep = 1"))
  private def selected(flag: Bool): Bool = {
    val wire = WireDefault(flag)
    addAttribute(wire, "keep = 1")
    wire
  }
  val shiftPairs = Seq(
    selected(op("SLL") && instr_first_cycle_i) -> leftDirect,
    selected(op("SRA") && instr_first_cycle_i) -> signedDirect,
    selected(op("SRL", "SLO", "SRO") && instr_first_cycle_i) -> rightDirect,
    selected(op("SLL", "SRA", "SRL", "SLO", "SRO") && !instr_first_cycle_i && amountZero) -> operand_a_i,
    selected(op("SLL") && !instr_first_cycle_i && !amountZero) -> leftComplement,
    selected(op("SRA") && !instr_first_cycle_i && !amountZero) -> signedComplement,
    selected(op("SRL", "SLO", "SRO") && !instr_first_cycle_i && !amountZero) -> rightComplement)

  val bwlogic_result = Mux(op("OR", "ORN"), operand_a_i | operand_b_i,
    Mux(op("AND", "ANDN"), operand_a_i & operand_b_i, operand_a_i ^ operand_b_i))
  imd_val_d_o := 0.U
  imd_val_we_o := 0.U
  result_o := Mux1H(shiftPairs ++ Seq(
    selected(op("XOR", "XNOR")) -> (operand_a_i ^ operand_b_i),
    selected(op("OR", "ORN")) -> (operand_a_i | operand_b_i),
    selected(op("AND", "ANDN")) -> (operand_a_i & operand_b_i),
    selected(op("ADD", "SUB", "SH1ADD", "SH2ADD", "SH3ADD")) -> result_adder,
    selected(op("EQ", "NE", "GE", "GEU", "LT", "LTU", "SLT", "SLTU")) -> Cat(0.U(31.W), result_cmp)))
}
