// Copyright lowRISC contributors. Licensed under Apache-2.0.
// SPDX-License-Identifier: Apache-2.0
// Translation of rtl/ibex_wb_stage.sv, Ibex
// 38c070939183cc10940b66c8e9e04eeca6b65470, pinned bypass configuration.
package deadhorse.perf_core

import chisel3._

class IbexWbStage(val ResetAll: Boolean = false, val WritebackStage: Boolean = false,
    val DummyInstructions: Boolean = false) extends RawModule {
  require(!ResetAll && !WritebackStage && !DummyInstructions,"T11 implements the pinned WB bypass")
  override def desiredName = "ibex_wb_stage"
  val clk_i=IO(Input(Clock())); val rst_ni=IO(Input(Bool()))
  val en_wb_i=IO(Input(Bool())); val instr_type_wb_i=IO(Input(UInt(2.W)))
  val pc_id_i=IO(Input(UInt(32.W))); val instr_is_compressed_id_i=IO(Input(Bool()))
  val instr_perf_count_id_i=IO(Input(Bool()))
  val ready_wb_o=IO(Output(Bool())); val rf_write_wb_o=IO(Output(Bool()))
  val outstanding_load_wb_o=IO(Output(Bool())); val outstanding_store_wb_o=IO(Output(Bool()))
  val pc_wb_o=IO(Output(UInt(32.W))); val perf_instr_ret_wb_o=IO(Output(Bool()))
  val perf_instr_ret_compressed_wb_o=IO(Output(Bool()))
  val perf_instr_ret_wb_spec_o=IO(Output(Bool())); val perf_instr_ret_compressed_wb_spec_o=IO(Output(Bool()))
  val rf_waddr_id_i=IO(Input(UInt(5.W))); val rf_wdata_id_i=IO(Input(UInt(32.W)))
  val rf_we_id_i=IO(Input(Bool())); val dummy_instr_id_i=IO(Input(Bool()))
  val rf_wdata_lsu_i=IO(Input(UInt(32.W))); val rf_we_lsu_i=IO(Input(Bool()))
  val rf_wdata_fwd_wb_o=IO(Output(UInt(32.W))); val rf_waddr_wb_o=IO(Output(UInt(5.W)))
  val rf_wdata_wb_o=IO(Output(UInt(32.W))); val rf_we_wb_o=IO(Output(Bool()))
  val dummy_instr_wb_o=IO(Output(Bool())); val lsu_resp_valid_i=IO(Input(Bool()))
  val lsu_resp_err_i=IO(Input(Bool())); val instr_done_wb_o=IO(Output(Bool()))
  rf_waddr_wb_o := rf_waddr_id_i
  // Preserve the masked OR, including the arbitrary-input simultaneous-write
  // case. No one-hot assumption is introduced at the translated boundary.
  rf_wdata_wb_o := Mux(rf_we_id_i,rf_wdata_id_i,0.U) | Mux(rf_we_lsu_i,rf_wdata_lsu_i,0.U)
  rf_we_wb_o := rf_we_id_i || rf_we_lsu_i
  dummy_instr_wb_o := dummy_instr_id_i
  perf_instr_ret_wb_o := instr_perf_count_id_i && en_wb_i && !(lsu_resp_valid_i && lsu_resp_err_i)
  perf_instr_ret_compressed_wb_o := perf_instr_ret_wb_o && instr_is_compressed_id_i
  perf_instr_ret_wb_spec_o := false.B; perf_instr_ret_compressed_wb_spec_o := false.B
  ready_wb_o := true.B; outstanding_load_wb_o := false.B; outstanding_store_wb_o := false.B
  pc_wb_o := 0.U; rf_write_wb_o := false.B; rf_wdata_fwd_wb_o := 0.U; instr_done_wb_o := false.B
}
