// Copyright lowRISC contributors.
// Copyright 2018 ETH Zurich and University of Bologna, see also upstream CREDITS.md.
// Licensed under the Apache License, Version 2.0; SPDX-License-Identifier: Apache-2.0
// Translation of rtl/ibex_multdiv_fast.sv,
// Ibex 38c070939183cc10940b66c8e9e04eeca6b65470, pinned RV32MFast configuration.
package deadhorse.perf_core

import chisel3._
import chisel3.util.{Cat, Fill, switch, is, addAttribute}

class IbexMultdivFast(val RV32M: Int = 2, val iterativeMultiply: Boolean = false,
    val localDivisionArithmetic: Boolean = false) extends RawModule {
  require(RV32M == 2, "T11 implements the pinned RV32MFast configuration")
  override def desiredName = "ibex_multdiv_fast"
  val clk_i = IO(Input(Clock()))
  val rst_ni = IO(Input(Bool()))
  val mult_en_i = IO(Input(Bool()))
  val div_en_i = IO(Input(Bool()))
  val mult_sel_i = IO(Input(Bool()))
  val div_sel_i = IO(Input(Bool()))
  val operator_i = IO(Input(UInt(2.W)))
  val signed_mode_i = IO(Input(UInt(2.W)))
  val op_a_i = IO(Input(UInt(32.W)))
  val op_b_i = IO(Input(UInt(32.W)))
  val alu_adder_ext_i = IO(Input(UInt(34.W)))
  val alu_adder_i = IO(Input(UInt(32.W)))
  val equal_to_zero_i = IO(Input(Bool()))
  val data_ind_timing_i = IO(Input(Bool()))
  val alu_operand_a_o = IO(Output(UInt(33.W)))
  val alu_operand_b_o = IO(Output(UInt(33.W)))
  val imd_val_q_i = IO(Input(UInt(68.W)))
  val imd_val_d_o = IO(Output(UInt(68.W)))
  val imd_val_we_o = IO(Output(UInt(2.W)))
  val multdiv_ready_id_i = IO(Input(Bool()))
  dontTouch(multdiv_ready_id_i) // Formal-only ALTOPS binding also observes completion acceptance.
  val multdiv_result_o = IO(Output(UInt(32.W)))
  val valid_o = IO(Output(Bool()))
  private val mull = 0.U(2.W)
  private val div = 2.U(2.W)
  private val idle = 0.U(3.W)
  private val absA = 1.U(3.W)
  private val absB = 2.U(3.W)
  private val comp = 3.U(3.W)
  private val last = 4.U(3.W)
  private val changeSign = 5.U(3.W)
  private val finish = 6.U(3.W)

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


  withClockAndReset(clk_i, (!rst_ni).asAsyncReset) {
    val div_counter_q = RegInit(0.U(5.W))
    val md_state_q = RegInit(idle)
    val op_numerator_q = RegInit(0.U(32.W))
    val op_quotient_q = RegInit(0.U(32.W))
    val div_by_zero_q = RegInit(false.B)
    // slang flattens the reference's ascending unpacked [0:1] array with
    // element zero in the high word; the separate packed write-enable stays LSB0.
    val intermediate = imd_val_q_i(67, 34)
    val op_denominator_q = imd_val_q_i(31, 0)

    // Keep the faithful default as an independently proved comparison target.
    // The explicitly approved iterative variant changes multiply latency only.
    val (mac_res_d, mult_valid, mult_en_internal) = if (iterativeMultiply) {
      val multiplier = Module(new IterativeMultiply)
      multiplier.clk_i := clk_i
      multiplier.rst_ni := rst_ni
      multiplier.enable_i := mult_en_i
      multiplier.ready_i := multdiv_ready_id_i
      multiplier.a_i := op_a_i
      multiplier.b_i := op_b_i
      multiplier.signed_mode_i := signed_mode_i
      multiplier.high_i := operator_i =/= mull
      (Cat(0.U(2.W), multiplier.result_o), multiplier.valid_o, false.B)
    } else {
      val mult_state_q = RegInit(0.U(2.W)).suggestName("gen_mult_fast_mult_state_q")
      // Stable observation point for the hash-bound, formal-only D44 adapter.
      val sva_mul_fsm_idle = WireDefault(mult_state_q === 0.U)
      dontTouch(sva_mul_fsm_idle)
      val mult_op_a = WireDefault(op_a_i(15, 0))
      val mult_op_b = WireDefault(op_b_i(15, 0))
      val sign_a = WireDefault(false.B)
      val sign_b = WireDefault(false.B)
      val accum = WireDefault(intermediate)
      // Keep the signed 17-bit product operator: the equivalence harness proves
      // its operand equality before using a shared symbolic product (D44).
      val product = Cat(sign_a, mult_op_a).asSInt * Cat(sign_b, mult_op_b).asSInt
      val mac_res_signed = product.pad(35) + accum.asSInt.pad(35)
      val mac_res_ext = mac_res_signed.asUInt
      val mac_res = mac_res_ext(33, 0)
      val mac_res_d = WireDefault(mac_res)
      val mult_state_d = WireDefault(mult_state_q)
      val mult_valid = WireDefault(false.B)
      val mult_hold = WireDefault(false.B)
      switch(mult_state_q) {
        is(0.U) {
          accum := 0.U
          mult_state_d := 1.U
        }
        is(1.U) {
          mult_op_b := op_b_i(31, 16)
          sign_b := signed_mode_i(1) && op_b_i(31)
          accum := Cat(0.U(18.W), intermediate(31, 16))
          when(operator_i === mull) { mac_res_d := Cat(0.U(2.W), mac_res(15, 0), intermediate(15, 0)) }
          mult_state_d := 2.U
        }
        is(2.U) {
          mult_op_a := op_a_i(31, 16)
          sign_a := signed_mode_i(0) && op_a_i(31)
          when(operator_i === mull) {
            accum := Cat(0.U(18.W), intermediate(31, 16))
            mac_res_d := Cat(0.U(2.W), mac_res(15, 0), intermediate(15, 0))
            mult_valid := true.B
            mult_state_d := 0.U
            mult_hold := !multdiv_ready_id_i
          }.otherwise { mult_state_d := 3.U }
        }
        is(3.U) {
          mult_op_a := op_a_i(31, 16)
          mult_op_b := op_b_i(31, 16)
          sign_a := signed_mode_i(0) && op_a_i(31)
          sign_b := signed_mode_i(1) && op_b_i(31)
          accum := Cat(Fill(16, signed_mode_i.orR && intermediate(33)), intermediate(33, 16))
          mult_valid := true.B
          mult_state_d := 0.U
          mult_hold := !multdiv_ready_id_i
        }
      }
      val mult_en_internal = mult_en_i && !mult_hold
      when(mult_en_internal) { mult_state_q := mult_state_d }
      (mac_res_d, mult_valid, mult_en_internal)
    }

    // Parent-level same-cycle repair: compute the fixed divider arithmetic
    // before state selection instead of feeding state-selected operands through
    // the shared ALU and back. Keep the original arbitrary-input behavior when
    // EX is not selecting mult/div. Exact equivalence is proved at EX boundary.
    val selected = mult_sel_i || div_sel_i
    val localDifference = if (localDivisionArithmetic)
      fastAdd(intermediate(31,0), ~op_denominator_q, 32, true.B) else 0.U(32.W)
    val localNegation = if (localDivisionArithmetic) {
      Mux(md_state_q === absA, fastAdd(~op_a_i, 0.U, 32, true.B),
        Mux(md_state_q === absB, fastAdd(~op_b_i, 0.U, 32, true.B),
          fastAdd(~intermediate(31,0), 0.U, 32, true.B)))
    } else 0.U(32.W)
    val res_adder_h = if (localDivisionArithmetic) Mux(selected, localDifference, alu_adder_ext_i(32,1))
      else alu_adder_ext_i(32,1)
    val divider_adder = if (localDivisionArithmetic) Mux(selected, localNegation, alu_adder_i) else alu_adder_i
    val is_greater_equal = Mux(intermediate(31) === op_denominator_q(31), !res_adder_h(31), intermediate(31))
    val next_remainder = Mux(is_greater_equal, res_adder_h, intermediate(31, 0))
    val one_shift = (1.U(32.W) << div_counter_q)(31, 0)
    val next_quotient = Cat(false.B, Mux(is_greater_equal, op_quotient_q | one_shift, op_quotient_q))
    val div_sign_a = op_a_i(31) && signed_mode_i(0)
    val div_sign_b = op_b_i(31) && signed_mode_i(1)
    val div_change_sign = (div_sign_a ^ div_sign_b) && !div_by_zero_q
    val div_counter_d = WireDefault(div_counter_q - 1.U(5.W))
    val op_remainder_d = WireDefault(intermediate)
    val op_quotient_d = WireDefault(op_quotient_q)
    val md_state_d = WireDefault(md_state_q)
    val op_numerator_d = WireDefault(op_numerator_q)
    val op_denominator_d = WireDefault(op_denominator_q)
    val div_valid = WireDefault(false.B)
    val div_hold = WireDefault(false.B)
    val div_by_zero_d = WireDefault(div_by_zero_q)
    alu_operand_a_o := 1.U(33.W)
    alu_operand_b_o := Cat(~op_b_i, true.B)
    when(md_state_q > finish) { md_state_d := idle }
    switch(md_state_q) {
      is(idle) {
        when(operator_i === div) {
          op_remainder_d := ((BigInt(1) << 34) - 1).U(34.W)
          div_by_zero_d := equal_to_zero_i
        }.otherwise { op_remainder_d := Cat(0.U(2.W), op_a_i) }
        md_state_d := Mux(!data_ind_timing_i && equal_to_zero_i, finish, absA)
        div_counter_d := 31.U
      }
      is(absA) {
        op_quotient_d := 0.U
        op_numerator_d := Mux(div_sign_a, divider_adder, op_a_i)
        md_state_d := absB
        div_counter_d := 31.U
        alu_operand_b_o := Cat(~op_a_i, true.B)
      }
      is(absB) {
        op_remainder_d := Cat(0.U(33.W), op_numerator_q(31))
        op_denominator_d := Mux(div_sign_b, divider_adder, op_b_i)
        md_state_d := comp
        div_counter_d := 31.U
      }
      is(comp) {
        op_remainder_d := Cat(false.B, next_remainder, op_numerator_q(div_counter_d))
        op_quotient_d := next_quotient(31, 0)
        md_state_d := Mux(div_counter_q === 1.U, last, comp)
        alu_operand_a_o := Cat(intermediate(31, 0), true.B)
        alu_operand_b_o := Cat(~op_denominator_q, true.B)
      }
      is(last) {
        op_remainder_d := Mux(operator_i === div, Cat(false.B, next_quotient), Cat(0.U(2.W), next_remainder))
        alu_operand_a_o := Cat(intermediate(31, 0), true.B)
        alu_operand_b_o := Cat(~op_denominator_q, true.B)
        md_state_d := changeSign
      }
      is(changeSign) {
        md_state_d := finish
        when(Mux(operator_i === div, div_change_sign, div_sign_a)) {
          op_remainder_d := Cat(0.U(2.W), divider_adder)
        }
        alu_operand_b_o := Cat(~intermediate(31, 0), true.B)
      }
      is(finish) {
        md_state_d := idle
        div_hold := !multdiv_ready_id_i
        div_valid := true.B
      }
    }
    val div_en_internal = div_en_i && !div_hold
    when(div_en_internal) {
      div_counter_q := div_counter_d
      op_numerator_q := op_numerator_d
      op_quotient_q := op_quotient_d
      md_state_q := md_state_d
      div_by_zero_q := div_by_zero_d
    }
    imd_val_d_o := Cat(Mux(div_sel_i, op_remainder_d, mac_res_d), 0.U(2.W), op_denominator_d)
    imd_val_we_o := Cat(div_en_internal, mult_en_internal || div_en_internal)
    multdiv_result_o := Mux(div_sel_i, intermediate(31, 0), mac_res_d(31, 0))
    valid_o := mult_valid || div_valid
  }
}
