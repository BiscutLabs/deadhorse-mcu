// Copyright lowRISC contributors.
// Copyright 2018 ETH Zurich and University of Bologna, see also upstream CREDITS.md.
// Licensed under the Apache License, Version 2.0; SPDX-License-Identifier: Apache-2.0
// Translation of rtl/ibex_prefetch_buffer.sv,
// Ibex 38c070939183cc10940b66c8e9e04eeca6b65470.
package deadhorse.perf_core

import chisel3._
import chisel3.util.{Cat, Reverse, addAttribute}

class IbexPrefetchBuffer(val ResetAll: Boolean = false) extends RawModule {
  override def desiredName = "ibex_prefetch_buffer"
  val clk_i = IO(Input(Clock()))
  val rst_ni = IO(Input(Bool()))
  val req_i = IO(Input(Bool()))
  val branch_i = IO(Input(Bool()))
  val addr_i = IO(Input(UInt(32.W)))
  val ready_i = IO(Input(Bool()))
  val valid_o = IO(Output(Bool()))
  val rdata_o = IO(Output(UInt(32.W)))
  val addr_o = IO(Output(UInt(32.W)))
  val err_o = IO(Output(Bool()))
  val err_plus2_o = IO(Output(Bool()))
  val instr_req_o = IO(Output(Bool()))
  val instr_gnt_i = IO(Input(Bool()))
  val instr_addr_o = IO(Output(UInt(32.W)))
  val instr_rdata_i = IO(Input(UInt(32.W)))
  val instr_err_i = IO(Input(Bool()))
  val instr_rvalid_i = IO(Input(Bool()))
  val busy_o = IO(Output(Bool()))

  withClockAndReset(clk_i, (!rst_ni).asAsyncReset) {
    val valid_req_q = RegInit(false.B)
    val discard_req_q = RegInit(false.B)
    val rdata_outstanding_q = RegInit(0.U(2.W))
    val branch_discard_q = RegInit(0.U(2.W))
    val stored_addr_q = if (ResetAll) RegInit(0.U(32.W)) else Reg(UInt(32.W))
    val fetch_addr_q = if (ResetAll) RegInit(0.U(32.W)) else Reg(UInt(32.W))
    val fifo_i = Module(new IbexFetchFifo(2, ResetAll))
    fifo_i.clk_i := clk_i
    fifo_i.rst_ni := rst_ni
    fifo_i.clear_i := branch_i
    fifo_i.in_valid_i := instr_rvalid_i && !branch_discard_q(0)
    fifo_i.in_addr_i := addr_i
    fifo_i.in_rdata_i := instr_rdata_i
    fifo_i.in_err_i := instr_err_i
    fifo_i.out_ready_i := ready_i
    valid_o := fifo_i.out_valid_o
    rdata_o := fifo_i.out_rdata_o
    addr_o := fifo_i.out_addr_o
    err_o := fifo_i.out_err_o
    err_plus2_o := fifo_i.out_err_plus2_o
    val fifo_ready = !(fifo_i.busy_o | Reverse(rdata_outstanding_q)).andR
    val valid_new_req = req_i && (fifo_ready || branch_i) && !rdata_outstanding_q(1)
    val valid_req = valid_req_q || valid_new_req
    val discard_req_d = valid_req_q && (branch_i || discard_req_q)
    valid_req_q := valid_req && !instr_gnt_i
    discard_req_q := discard_req_d
    val instr_addr = Mux(valid_req_q, stored_addr_q, Mux(branch_i, addr_i, fetch_addr_q))
    when(valid_new_req && !valid_req_q && !instr_gnt_i) { stored_addr_q := instr_addr }
    // Approved same-state timing repair: advance both address candidates
    // before selecting the redirect. Neither request nor redirect control
    // enters a carry chain; all original update/hold conditions are retained.
    def advance(base: UInt): UInt = {
      val chunks = (2 until 32 by 4).map { low =>
        val high = math.min(low + 3, 31)
        val word = base(high, low)
        val incremented = WireDefault(word + 1.U((high - low + 1).W))
        addAttribute(incremented, "keep = 1")
        val carry = WireDefault(if (low == 2) true.B else base(low - 1, 2).andR)
        addAttribute(carry, "keep = 1")
        Mux(carry, incremented, word)
      }
      Cat(Cat(chunks.reverse), base(1, 0))
    }
    val sequential_base = Cat(fetch_addr_q(31, 2), 0.U(2.W))
    val step = valid_new_req && !valid_req_q
    val fetch_addr_d = Mux(branch_i, Mux(step, advance(addr_i), addr_i),
      Mux(step, advance(sequential_base), sequential_base))
    when(branch_i || (valid_new_req && !valid_req_q)) { fetch_addr_q := fetch_addr_d }
    val rdata_outstanding_n = Cat((valid_req && instr_gnt_i && rdata_outstanding_q(0)) || rdata_outstanding_q(1),
      (valid_req && instr_gnt_i) || rdata_outstanding_q(0))
    val branch_discard_n = Cat(
      (valid_req && instr_gnt_i && discard_req_d && rdata_outstanding_q(0)) ||
        (branch_i && rdata_outstanding_q(1)) || branch_discard_q(1),
      (valid_req && instr_gnt_i && discard_req_d) || (branch_i && rdata_outstanding_q(0)) || branch_discard_q(0))
    rdata_outstanding_q := Mux(instr_rvalid_i, Cat(false.B, rdata_outstanding_n(1)), rdata_outstanding_n)
    branch_discard_q := Mux(instr_rvalid_i, Cat(false.B, branch_discard_n(1)), branch_discard_n)
    busy_o := rdata_outstanding_q.orR || valid_req
    instr_req_o := valid_req
    instr_addr_o := Cat(instr_addr(31, 2), 0.U(2.W))
  }
}
