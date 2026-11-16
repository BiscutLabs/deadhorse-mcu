// Copyright lowRISC contributors.
// Copyright 2018 ETH Zurich and University of Bologna; see upstream CREDITS.md.
// Licensed under Apache-2.0; SPDX-License-Identifier: Apache-2.0
// Translation of rtl/ibex_load_store_unit.sv, Ibex
// 38c070939183cc10940b66c8e9e04eeca6b65470, pinned MemECC=false configuration.
package deadhorse.perf_core

import chisel3._
import chisel3.util.{Cat, Fill, MuxLookup, is, switch}

class IbexLoadStoreUnit(val MemECC: Boolean = false, val MemDataWidth: Int = 32) extends RawModule {
  require(!MemECC && MemDataWidth == 32,"T11 implements the pinned non-ECC LSU")
  override def desiredName = "ibex_load_store_unit"
  val clk_i = IO(Input(Clock())); val rst_ni = IO(Input(Bool()))
  val data_req_o = IO(Output(Bool())); val data_gnt_i = IO(Input(Bool()))
  val data_rvalid_i = IO(Input(Bool())); val data_bus_err_i = IO(Input(Bool()))
  val data_pmp_err_i = IO(Input(Bool()))
  val data_addr_o = IO(Output(UInt(32.W))); val data_we_o = IO(Output(Bool()))
  val data_be_o = IO(Output(UInt(4.W))); val data_wdata_o = IO(Output(UInt(32.W)))
  val data_rdata_i = IO(Input(UInt(32.W)))
  val lsu_we_i = IO(Input(Bool())); val lsu_type_i = IO(Input(UInt(2.W)))
  val lsu_wdata_i = IO(Input(UInt(32.W))); val lsu_sign_ext_i = IO(Input(Bool()))
  val lsu_rdata_o = IO(Output(UInt(32.W))); val lsu_rdata_valid_o = IO(Output(Bool()))
  val lsu_req_i = IO(Input(Bool())); val adder_result_ex_i = IO(Input(UInt(32.W)))
  val addr_incr_req_o = IO(Output(Bool())); val addr_last_o = IO(Output(UInt(32.W)))
  val lsu_req_done_o = IO(Output(Bool())); val lsu_resp_valid_o = IO(Output(Bool()))
  val load_err_o = IO(Output(Bool())); val load_resp_intg_err_o = IO(Output(Bool()))
  val store_err_o = IO(Output(Bool())); val store_resp_intg_err_o = IO(Output(Bool()))
  val busy_o = IO(Output(Bool())); val perf_load_o = IO(Output(Bool())); val perf_store_o = IO(Output(Bool()))

  private val idle = 0.U(3.W); private val waitGntMis = 1.U(3.W)
  private val waitRvalidMis = 2.U(3.W); private val waitGnt = 3.U(3.W)
  private val waitRvalidMisGntsDone = 4.U(3.W)
  withClockAndReset(clk_i,(!rst_ni).asAsyncReset) {
    val ls_fsm_cs = RegInit(idle)
    val handle_misaligned_q = RegInit(false.B)
    val pmp_err_q = RegInit(false.B); val lsu_err_q = RegInit(false.B)
    val rdata_q = RegInit(0.U(24.W))
    val rdata_offset_q = RegInit(0.U(2.W)); val data_type_q = RegInit(0.U(2.W))
    val data_sign_ext_q = RegInit(false.B); val data_we_q = RegInit(false.B)
    val addr_last_q = RegInit(0.U(32.W))
    val ls_fsm_ns = WireDefault(ls_fsm_cs)
    val handle_misaligned_d = WireDefault(handle_misaligned_q)
    val pmp_err_d = WireDefault(pmp_err_q); val lsu_err_d = WireDefault(lsu_err_q)
    val addr_update = WireDefault(false.B); val ctrl_update = WireDefault(false.B)
    val rdata_update = WireDefault(false.B)
    val offset = adder_result_ex_i(1,0)
    val aligned = Cat(adder_result_ex_i(31,2),0.U(2.W))
    val split = (lsu_type_i === 0.U && offset =/= 0.U) || (lsu_type_i === 1.U && offset === 3.U)

    // Byte lanes and cyclic write-data alignment preserve the reference's
    // behavior even for otherwise-unused size/offset combinations.
    val wordMask = Mux(handle_misaligned_q,
      MuxLookup(offset,0.U(4.W))(Seq(1.U->1.U(4.W),2.U->3.U(4.W),3.U->7.U(4.W))),
      MuxLookup(offset,15.U(4.W))(Seq(1.U->14.U(4.W),2.U->12.U(4.W),3.U->8.U(4.W))))
    val halfMask = Mux(handle_misaligned_q,1.U(4.W),
      MuxLookup(offset,3.U(4.W))(Seq(1.U->6.U(4.W),2.U->12.U(4.W),3.U->8.U(4.W))))
    data_be_o := Mux(lsu_type_i === 0.U,wordMask,Mux(lsu_type_i === 1.U,halfMask,(1.U(4.W)<<offset)(3,0)))
    data_wdata_o := MuxLookup(offset,lsu_wdata_i)(Seq(
      1.U -> Cat(lsu_wdata_i(23,0),lsu_wdata_i(31,24)),
      2.U -> Cat(lsu_wdata_i(15,0),lsu_wdata_i(31,16)),
      3.U -> Cat(lsu_wdata_i(7,0),lsu_wdata_i(31,8))))
    val readWord = MuxLookup(rdata_offset_q,data_rdata_i)(Seq(
      1.U -> Cat(data_rdata_i(7,0),rdata_q),
      2.U -> Cat(data_rdata_i(15,0),rdata_q(23,8)),
      3.U -> Cat(data_rdata_i(23,0),rdata_q(23,16))))
    val readHalf = MuxLookup(rdata_offset_q,data_rdata_i(15,0))(Seq(
      1.U -> data_rdata_i(23,8), 2.U -> data_rdata_i(31,16),
      3.U -> Cat(data_rdata_i(7,0),rdata_q(23,16))))
    val readByte = MuxLookup(rdata_offset_q,data_rdata_i(7,0))(Seq(
      1.U -> data_rdata_i(15,8),2.U -> data_rdata_i(23,16),3.U -> data_rdata_i(31,24)))
    lsu_rdata_o := Mux(data_type_q === 0.U,readWord,
      Mux(data_type_q === 1.U,Cat(Fill(16,data_sign_ext_q && readHalf(15)),readHalf),
        Cat(Fill(24,data_sign_ext_q && readByte(7)),readByte)))

    data_req_o := false.B; addr_incr_req_o := false.B
    perf_load_o := false.B; perf_store_o := false.B
    switch(ls_fsm_cs) {
      is(idle) {
        pmp_err_d := false.B
        when(lsu_req_i) {
          data_req_o := true.B; pmp_err_d := data_pmp_err_i; lsu_err_d := false.B
          perf_load_o := !lsu_we_i; perf_store_o := lsu_we_i
          when(data_gnt_i) {
            ctrl_update := true.B; addr_update := true.B; handle_misaligned_d := split
            ls_fsm_ns := Mux(split,waitRvalidMis,idle)
          }.otherwise { ls_fsm_ns := Mux(split,waitGntMis,waitGnt) }
        }
      }
      is(waitGntMis) {
        data_req_o := true.B
        when(data_gnt_i || pmp_err_q) {
          addr_update := true.B; ctrl_update := true.B; handle_misaligned_d := true.B
          ls_fsm_ns := waitRvalidMis
        }
      }
      is(waitRvalidMis) {
        data_req_o := true.B; addr_incr_req_o := true.B
        when(data_rvalid_i || pmp_err_q) {
          pmp_err_d := data_pmp_err_i; lsu_err_d := data_bus_err_i || pmp_err_q
          rdata_update := !data_we_q; ls_fsm_ns := Mux(data_gnt_i,idle,waitGnt)
          addr_update := data_gnt_i && !(data_bus_err_i || pmp_err_q)
          handle_misaligned_d := !data_gnt_i
        }.elsewhen(data_gnt_i) {
          ls_fsm_ns := waitRvalidMisGntsDone; handle_misaligned_d := false.B
        }
      }
      is(waitGnt) {
        addr_incr_req_o := handle_misaligned_q; data_req_o := true.B
        when(data_gnt_i || pmp_err_q) {
          ctrl_update := true.B; addr_update := !lsu_err_q; ls_fsm_ns := idle
          handle_misaligned_d := false.B
        }
      }
      is(waitRvalidMisGntsDone) {
        addr_incr_req_o := true.B
        when(data_rvalid_i) {
          pmp_err_d := data_pmp_err_i; lsu_err_d := data_bus_err_i
          addr_update := !data_bus_err_i; rdata_update := !data_we_q; ls_fsm_ns := idle
        }
      }
    }
    when(ls_fsm_cs > waitRvalidMisGntsDone) { ls_fsm_ns := idle }
    ls_fsm_cs := ls_fsm_ns; handle_misaligned_q := handle_misaligned_d
    pmp_err_q := pmp_err_d; lsu_err_q := lsu_err_d
    when(rdata_update) { rdata_q := data_rdata_i(31,8) }
    when(ctrl_update) {
      rdata_offset_q := offset; data_type_q := lsu_type_i
      data_sign_ext_q := lsu_sign_ext_i; data_we_q := lsu_we_i
    }
    when(addr_update) { addr_last_q := Mux(addr_incr_req_o,aligned,adder_result_ex_i) }
    val error = lsu_err_q || data_bus_err_i || pmp_err_q
    lsu_req_done_o := (lsu_req_i || ls_fsm_cs =/= idle) && ls_fsm_ns === idle
    lsu_resp_valid_o := (data_rvalid_i || pmp_err_q) && ls_fsm_cs === idle
    lsu_rdata_valid_o := ls_fsm_cs === idle && data_rvalid_i && !error && !data_we_q
    data_addr_o := aligned; data_we_o := lsu_we_i; addr_last_o := addr_last_q
    load_err_o := error && !data_we_q && lsu_resp_valid_o
    store_err_o := error && data_we_q && lsu_resp_valid_o
    load_resp_intg_err_o := false.B; store_resp_intg_err_o := false.B
    busy_o := ls_fsm_cs =/= idle
  }
}
