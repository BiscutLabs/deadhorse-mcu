// Copyright lowRISC contributors.
// Licensed under the Apache License, Version 2.0; SPDX-License-Identifier: Apache-2.0
// Translation of rtl/ibex_csr.sv, Ibex 38c070939183cc10940b66c8e9e04eeca6b65470.
package deadhorse.perf_core

import chisel3._

class IbexCsr(val Width: Int = 32, val ShadowCopy: Boolean = false,
              val ResetValue: BigInt = 0) extends RawModule {
  require(Width > 0 && ResetValue >= 0 && ResetValue < (BigInt(1) << Width))
  override def desiredName = "ibex_csr"
  val clk_i = IO(Input(Clock()))
  val rst_ni = IO(Input(Bool()))
  val wr_data_i = IO(Input(UInt(Width.W)))
  val wr_en_i = IO(Input(Bool()))
  val rd_data_o = IO(Output(UInt(Width.W)))
  val rd_error_o = IO(Output(Bool()))

  withClockAndReset(clk_i, (!rst_ni).asAsyncReset) {
    val rdata_q = RegInit(ResetValue.U(Width.W))
    when(wr_en_i) { rdata_q := wr_data_i }
    rd_data_o := rdata_q
    if (ShadowCopy) {
      val shadow_q = RegInit(((BigInt(1) << Width) - 1 - ResetValue).U(Width.W))
        .suggestName("gen_shadow_shadow_q")
      when(wr_en_i) { shadow_q := ~wr_data_i }
      rd_error_o := rdata_q =/= ~shadow_q
    } else {
      rd_error_o := false.B
    }
  }
}
