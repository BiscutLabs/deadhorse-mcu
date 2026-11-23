// Copyright lowRISC contributors; ETH Zurich and University of Bologna.
// Licensed under Apache-2.0. SPDX-License-Identifier: Apache-2.0
// Translation of rtl/ibex_top.sv, Ibex
// 38c070939183cc10940b66c8e9e04eeca6b65470, pinned two-stage configuration.
package deadhorse.perf_core

import chisel3._
import chisel3.reflect.DataMirror
import deadhorse.lib.{ClockGate,ClockGateTarget}

class IbexTop(val gateTarget: ClockGateTarget = ClockGateTarget.Asic,
    val WithRVFI: Boolean = true, val RegisteredExecution: Boolean = false, val WithF: Boolean = false,
    DmHaltAddr: BigInt=BigInt("1a110800",16),DmExceptionAddr: BigInt=BigInt("1a110808",16)) extends RawModule {
  override def desiredName="ibex_top"
  val clk_i=IO(Input(Clock())); val rst_ni=IO(Input(Bool())); val test_en_i=IO(Input(Bool()))
  val ram_cfg_i=IO(Input(UInt(10.W))); val scan_rst_ni=IO(Input(Bool()))
  val instr_rdata_intg_i=IO(Input(UInt(7.W))); val data_rdata_intg_i=IO(Input(UInt(7.W)))
  val data_wdata_intg_o=IO(Output(UInt(7.W)))
  val scramble_key_valid_i=IO(Input(Bool())); val scramble_key_i=IO(Input(UInt(128.W)))
  val scramble_nonce_i=IO(Input(UInt(64.W))); val scramble_req_o=IO(Output(Bool()))
  val debug_mode_o=IO(Output(Bool()))
  val core_sleep_o=IO(Output(Bool()))
  val u_ibex_core=Module(new IbexCore(WithRVFI=WithRVFI,RegisteredExecution=RegisteredExecution,WithF=WithF,DmHaltAddr=DmHaltAddr,DmExceptionAddr=DmExceptionAddr))
  val gen_regfile_ff_register_file_i=Module(new IbexRegisterFile)
  val core_clock_gate_i=Module(new ClockGate(gateTarget))
  debug_mode_o:=u_ibex_core.debug_mode_o
  val core=u_ibex_core; val rf=gen_regfile_ff_register_file_i

  // Re-export only the named reference ports common to core and top. This
  // preserves width/direction of RVFI arrays and keeps the list reviewable.
  val common=Set("hart_id_i","boot_addr_i","instr_req_o","instr_gnt_i","instr_rvalid_i",
    "instr_addr_o","instr_rdata_i","instr_err_i","data_req_o","data_gnt_i","data_rvalid_i",
    "data_we_o","data_be_o","data_addr_o","data_wdata_o","data_rdata_i","data_err_i",
    "irq_software_i","irq_timer_i","irq_external_i","irq_fast_i","irq_nm_i","debug_req_i",
    "crash_dump_o","double_fault_seen_o","fetch_enable_i","alert_minor_o","alert_major_internal_o","alert_major_bus_o")
  val corePorts=DataMirror.modulePorts(core).toMap
  require(common.subsetOf(corePorts.keySet))
  val ports=corePorts.toSeq.sortBy(_._1).filter { case(name,_)=>common(name) || name.startsWith("rvfi_") }
    .map { case(name,child)=>
      val parent=IO(chiselTypeOf(child)).suggestName(name)
      if(DataMirror.directionOf(child)==ActualDirection.Input) child:=parent else parent:=child
      name->parent
    }.toMap

  val core_busy_q=withClockAndReset(clk_i,(!rst_ni).asAsyncReset) { RegNext(core.core_busy_o,10.U(4.W)) }
  val clock_en=core_busy_q(0) || ports("debug_req_i").asUInt.asBool || core.irq_pending_o || ports("irq_nm_i").asUInt.asBool
  core_sleep_o:= !clock_en
  core_clock_gate_i.clk_i:=clk_i; core_clock_gate_i.en_i:=clock_en; core_clock_gate_i.test_en_i:=test_en_i
  core.clk_i:=core_clock_gate_i.clk_o; core.rst_ni:=rst_ni
  rf.clk_i:=core_clock_gate_i.clk_o; rf.rst_ni:=rst_ni; rf.test_en_i:=test_en_i
  rf.dummy_instr_id_i:=core.dummy_instr_id_o; rf.dummy_instr_wb_i:=core.dummy_instr_wb_o
  rf.raddr_a_i:=core.rf_raddr_a_o; rf.raddr_b_i:=core.rf_raddr_b_o
  rf.waddr_a_i:=core.rf_waddr_wb_o; rf.wdata_a_i:=core.rf_wdata_wb_ecc_o; rf.we_a_i:=core.rf_we_wb_o
  core.rf_rdata_a_ecc_i:=rf.rdata_a_o; core.rf_rdata_b_ecc_i:=rf.rdata_b_o
  // Disabled cache/scrambling/ECC/lockstep: exact pinned tie-offs. RF integrity
  // error is identically false in the already-proved nonsecure register file.
  core.ic_tag_rdata_i:=0.U; core.ic_data_rdata_i:=0.U; core.ic_scr_key_valid_i:=true.B
  data_wdata_intg_o:=0.U; scramble_req_o:=false.B
}
