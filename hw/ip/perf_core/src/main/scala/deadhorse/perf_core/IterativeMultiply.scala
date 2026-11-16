// Copyright 2026 Deadhorse contributors.
// Licensed under the Apache License, Version 2.0; SPDX-License-Identifier: Apache-2.0
package deadhorse.perf_core

import chisel3._
import chisel3.util.{Cat, addAttribute, is, switch}

/** Approved latency-changing implementation; see ITERATIVE-MULTIPLIER.md. */
class IterativeMultiply extends RawModule {
  val clk_i = IO(Input(Clock()))
  val rst_ni = IO(Input(Bool()))
  val enable_i = IO(Input(Bool()))
  val ready_i = IO(Input(Bool()))
  val a_i = IO(Input(UInt(32.W)))
  val b_i = IO(Input(UInt(32.W)))
  val signed_mode_i = IO(Input(UInt(2.W)))
  val high_i = IO(Input(Bool()))
  val result_o = IO(Output(UInt(32.W)))
  val valid_o = IO(Output(Bool()))

  // Short local additions with a balanced prefix carry network. The 33rd
  // bit is essential: discarding it before the right shift loses products.
  private def add33(a: UInt, b: UInt, carryIn: Bool): UInt = {
    def keep(x: UInt): UInt = {
      val w = WireDefault(x)
      addAttribute(w, "keep = 1")
      w
    }
    val groups = (0 until 8).map { i =>
      val x = a(4*i+3, 4*i)
      val y = b(4*i+3, 4*i)
      (keep(x +& y), keep((x ^ y).andR.asUInt).asBool)
    }
    def prefix(gs: Seq[(UInt, Bool)]): (Bool, Bool) = {
      if (gs.size == 1) (gs.head._1(4), gs.head._2)
      else {
        val (gl, pl) = prefix(gs.take(gs.size/2))
        val (gh, ph) = prefix(gs.drop(gs.size/2))
        (keep((gh || (ph && gl)).asUInt).asBool,
          keep((ph && pl).asUInt).asBool)
      }
    }
    def carry(i: Int): Bool = if (i == 0) carryIn else {
      val (g, p) = prefix(groups.take(i))
      g || (p && carryIn)
    }
    val slices = groups.zipWithIndex.map { case ((sum, _), i) =>
      Mux(carry(i), keep(sum(3,0) + 1.U(4.W)), sum(3,0))
    }
    Cat(carry(8), Cat(slices.reverse))
  }

  withClockAndReset(clk_i, (!rst_ni).asAsyncReset) {
    val state_q = RegInit(0.U(3.W))
    val sva_mul_fsm_idle=WireDefault(state_q===0.U)
    dontTouch(sva_mul_fsm_idle)
    val count_q = RegInit(0.U(5.W))
    val a_q = RegInit(0.U(32.W))
    val b_q = RegInit(0.U(32.W))
    val hi_q = RegInit(0.U(32.W))
    val lo_q = RegInit(0.U(32.W))
    val sign_q = RegInit(0.U(2.W))
    val high_q = RegInit(false.B)
    val result_q = RegInit(0.U(32.W))
    val correction = state_q === 2.U || state_q === 3.U
    val subtract = Mux(state_q === 2.U, Mux(sign_q(0), b_q, 0.U),
      Mux(sign_q(1), a_q, 0.U))
    val term = Mux(correction, ~subtract, Mux(lo_q(0), a_q, 0.U))
    val sum = add33(hi_q, term, correction)
    when(enable_i) {
      switch(state_q) {
        is(0.U) {
          a_q := a_i
          b_q := b_i
          hi_q := 0.U
          lo_q := b_i
          sign_q := Cat(signed_mode_i(1) && b_i(31), signed_mode_i(0) && a_i(31))
          high_q := high_i
          count_q := 0.U
          state_q := 1.U
        }
        is(1.U) {
          hi_q := sum(32,1)
          lo_q := Cat(sum(0), lo_q(31,1))
          count_q := count_q + 1.U
          when(count_q === 31.U) { state_q := 2.U }
        }
        is(2.U) { hi_q := sum(31,0); state_q := 3.U }
        is(3.U) {
          hi_q := sum(31,0)
          result_q := Mux(high_q, sum(31,0), lo_q)
          state_q := 4.U
        }
        is(4.U) { when(ready_i) { state_q := 0.U } }
      }
    }
    valid_o := state_q === 4.U
    result_o := result_q
  }
}
