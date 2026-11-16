// Copyright lowRISC contributors.
// Copyright 2018 ETH Zurich and University of Bologna, see also upstream CREDITS.md.
// Licensed under the Apache License, Version 2.0; SPDX-License-Identifier: Apache-2.0
// Translation of rtl/ibex_register_file_ff.sv,
// Ibex 38c070939183cc10940b66c8e9e04eeca6b65470, pinned non-secure FF configuration.
package deadhorse.perf_core

import chisel3._

class IbexRegisterFile(val RV32E: Boolean = false, val DataWidth: Int = 32,
                       val DummyInstructions: Boolean = false,
                       val WrenCheck: Boolean = false, val RdataMuxCheck: Boolean = false,
                       val WordZeroVal: BigInt = 0) extends RawModule {
  require(!RV32E && !WrenCheck && !RdataMuxCheck,
    "T11 implements the pinned full-register, non-secure configuration")
  require(DataWidth > 0 && WordZeroVal >= 0 && WordZeroVal < (BigInt(1) << DataWidth))
  override def desiredName = "ibex_register_file_ff"
  val clk_i = IO(Input(Clock()))
  val rst_ni = IO(Input(Bool()))
  val test_en_i = IO(Input(Bool()))
  val dummy_instr_id_i = IO(Input(Bool()))
  val dummy_instr_wb_i = IO(Input(Bool()))
  val raddr_a_i = IO(Input(UInt(5.W)))
  val rdata_a_o = IO(Output(UInt(DataWidth.W)))
  val raddr_b_i = IO(Input(UInt(5.W)))
  val rdata_b_o = IO(Output(UInt(DataWidth.W)))
  val waddr_a_i = IO(Input(UInt(5.W)))
  val wdata_a_i = IO(Input(UInt(DataWidth.W)))
  val we_a_i = IO(Input(Bool()))
  val err_o = IO(Output(Bool()))

  val rf_reg = Wire(Vec(32, UInt(DataWidth.W)))
  withClockAndReset(clk_i, (!rst_ni).asAsyncReset) {
    for (index <- 1 until 32) {
      val rf_reg_q = RegInit(WordZeroVal.U(DataWidth.W))
        .suggestName(s"g_rf_flops_${index}_rf_reg_q")
      when(we_a_i && waddr_a_i === index.U) { rf_reg_q := wdata_a_i }
      rf_reg(index) := rf_reg_q
    }
    if (DummyInstructions) {
      val rf_r0_q = RegInit(WordZeroVal.U(DataWidth.W)).suggestName("g_dummy_r0_rf_r0_q")
      when(we_a_i && dummy_instr_wb_i) { rf_r0_q := wdata_a_i }
      rf_reg(0) := Mux(dummy_instr_id_i, rf_r0_q, WordZeroVal.U(DataWidth.W))
    } else {
      rf_reg(0) := WordZeroVal.U(DataWidth.W)
    }
  }
  rdata_a_o := rf_reg(raddr_a_i)
  rdata_b_o := rf_reg(raddr_b_i)
  err_o := false.B
}
