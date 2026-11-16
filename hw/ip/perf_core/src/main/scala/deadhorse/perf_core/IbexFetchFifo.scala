// Copyright lowRISC contributors.
// Copyright 2018 ETH Zurich and University of Bologna, see also upstream CREDITS.md.
// Licensed under the Apache License, Version 2.0; SPDX-License-Identifier: Apache-2.0
// Translation of rtl/ibex_fetch_fifo.sv,
// Ibex 38c070939183cc10940b66c8e9e04eeca6b65470.
package deadhorse.perf_core

import chisel3._
import chisel3.util.{Cat, addAttribute}

class IbexFetchFifo(val NUM_REQS: Int = 2, val ResetAll: Boolean = false) extends RawModule {
  require(NUM_REQS >= 1)
  override def desiredName = "ibex_fetch_fifo"
  val clk_i = IO(Input(Clock()))
  val rst_ni = IO(Input(Bool()))
  val clear_i = IO(Input(Bool()))
  val busy_o = IO(Output(UInt(NUM_REQS.W)))
  val in_valid_i = IO(Input(Bool()))
  val in_addr_i = IO(Input(UInt(32.W)))
  val in_rdata_i = IO(Input(UInt(32.W)))
  val in_err_i = IO(Input(Bool()))
  val out_valid_o = IO(Output(Bool()))
  val out_ready_i = IO(Input(Bool()))
  val out_addr_o = IO(Output(UInt(32.W)))
  val out_rdata_o = IO(Output(UInt(32.W)))
  val out_err_o = IO(Output(Bool()))
  val out_err_plus2_o = IO(Output(Bool()))
  private val depth = NUM_REQS + 1

  withClockAndReset(clk_i, (!rst_ni).asAsyncReset) {
    val valid_q = RegInit(0.U(depth.W))
    val instr_addr_q = if (ResetAll) RegInit(0.U(31.W)) else Reg(UInt(31.W))
    val words = (0 until depth).map { index =>
      (if (ResetAll) RegInit(0.U(32.W)) else Reg(UInt(32.W))).suggestName(s"rdata_word_$index")
    }
    val errors = (0 until depth).map { index =>
      (if (ResetAll) RegInit(false.B) else Reg(Bool())).suggestName(s"err_word_$index")
    }
    // Packed named aliases preserve the reference's bit-to-state correspondence.
    val rdata_q = WireDefault(Cat(words.reverse))
    val err_q = WireDefault(Cat(errors.reverse))
    val rdata = Mux(valid_q(0), rdata_q(31, 0), in_rdata_i)
    val err = Mux(valid_q(0), err_q(0), in_err_i)
    val valid = valid_q(0) || in_valid_i
    val unaligned_is_compressed = rdata(17, 16) =/= 3.U && !err
    val aligned_is_compressed = rdata(1, 0) =/= 3.U && !err
    val rdata_unaligned = Cat(Mux(valid_q(1), rdata_q(47, 32), in_rdata_i(15, 0)), rdata(31, 16))
    val err_unaligned = Mux(valid_q(1), (err_q(1) && !unaligned_is_compressed) || err_q(0),
      (valid_q(0) && err_q(0)) || (in_err_i && (!valid_q(0) || !unaligned_is_compressed)))
    val err_plus2 = Mux(valid_q(1), err_q(1) && !err_q(0), in_err_i && valid_q(0) && !err_q(0))
    val valid_unaligned = valid_q(1) || (valid_q(0) && in_valid_i)
    out_addr_o := Cat(instr_addr_q, false.B)
    out_rdata_o := Mux(out_addr_o(1), rdata_unaligned, rdata)
    out_err_o := Mux(out_addr_o(1), err_unaligned, err)
    out_err_plus2_o := out_addr_o(1) && err_plus2
    out_valid_o := Mux(out_addr_o(1) && !unaligned_is_compressed, valid_unaligned, valid)

    val instr_addr_en = clear_i || (out_ready_i && out_valid_o)
    val addr_incr_two = Mux(instr_addr_q(0), unaligned_is_compressed, aligned_is_compressed)
    // Approved same-state repair after the faithful increment failed timing.
    // In halfword units the increment is one or two. Resolve its first carry
    // once, then select independent local increments of the upper address.
    val carry_one = !addr_incr_two || instr_addr_q(0)
    val upper = (1 until 31 by 4).map { low =>
      val high = math.min(low + 3, 30)
      val word = instr_addr_q(high, low)
      val incremented = WireDefault(word + 1.U((high - low + 1).W))
      addAttribute(incremented, "keep = 1")
      val propagated = WireDefault(if (low == 1) true.B else instr_addr_q(low - 1, 1).andR)
      addAttribute(propagated, "keep = 1")
      Mux(carry_one && propagated, incremented, word)
    }
    val instr_addr_next = Cat(Cat(upper.reverse), instr_addr_q(0) ^ addr_incr_two)
    when(instr_addr_en) { instr_addr_q := Mux(clear_i, in_addr_i(31, 1), instr_addr_next) }
    busy_o := valid_q(depth - 1, 1)
    val pop_fifo = out_ready_i && out_valid_o && (!aligned_is_compressed || out_addr_o(1))
    val lowest_free_entry = (0 until depth).map { index =>
      !valid_q(index) && (if (index == 0) true.B else valid_q(index - 1))
    }
    val valid_pushed = (0 until depth).map { index =>
      valid_q(index) || (in_valid_i && lowest_free_entry(index))
    }
    val valid_d = (0 until depth).map { index =>
      val afterPop = if (index == depth - 1) false.B else valid_pushed(index + 1)
      Mux(pop_fifo, afterPop, valid_pushed(index)) && !clear_i
    }
    valid_q := Cat(valid_d.reverse)
    for (index <- 0 until depth) {
      val top = index == depth - 1
      val entry_en = if (top) in_valid_i && lowest_free_entry(index) else
        (valid_pushed(index + 1) && pop_fifo) || (in_valid_i && lowest_free_entry(index) && !pop_fifo)
      val rdata_d = if (top) in_rdata_i else Mux(valid_q(index + 1), words(index + 1), in_rdata_i)
      val err_d = if (top) in_err_i else Mux(valid_q(index + 1), errors(index + 1), in_err_i)
      when(entry_en) {
        words(index) := rdata_d
        errors(index) := err_d
      }
    }
  }
}
