// Copyright lowRISC contributors; ETH Zurich and University of Bologna.
// Licensed under Apache-2.0. SPDX-License-Identifier: Apache-2.0
// Translation of rtl/ibex_core.sv, Ibex
// 38c070939183cc10940b66c8e9e04eeca6b65470. Faithful, unretimed baseline.
package deadhorse.perf_core

import chisel3._
import chisel3.util._
import chisel3.util.experimental.BoringUtils

class IbexCore(val DbgTriggerEn: Boolean = true, val WithRVFI: Boolean = true,
    val DmHaltAddr: BigInt = BigInt("1a110800",16),
    val DmExceptionAddr: BigInt = BigInt("1a110808",16),
    val RegisteredExecution: Boolean = false, val WithF: Boolean = false) extends RawModule {
  require(DbgTriggerEn, "T11 core implements the pinned debug-trigger configuration")
  override def desiredName = "ibex_core"
  val clk_i=IO(Input(Clock())); val rst_ni=IO(Input(Bool()))
  val hart_id_i=IO(Input(UInt(32.W))); val boot_addr_i=IO(Input(UInt(32.W)))
  val instr_req_o=IO(Output(Bool())); val instr_gnt_i=IO(Input(Bool()))
  val instr_rvalid_i=IO(Input(Bool())); val instr_addr_o=IO(Output(UInt(32.W)))
  val instr_rdata_i=IO(Input(UInt(32.W))); val instr_err_i=IO(Input(Bool()))
  val data_req_o=IO(Output(Bool())); val data_gnt_i=IO(Input(Bool()))
  val data_rvalid_i=IO(Input(Bool())); val data_we_o=IO(Output(Bool()))
  val data_be_o=IO(Output(UInt(4.W))); val data_addr_o=IO(Output(UInt(32.W)))
  val data_wdata_o=IO(Output(UInt(32.W))); val data_rdata_i=IO(Input(UInt(32.W)))
  val data_err_i=IO(Input(Bool()))
  val dummy_instr_id_o=IO(Output(Bool())); val dummy_instr_wb_o=IO(Output(Bool()))
  val rf_raddr_a_o=IO(Output(UInt(5.W))); val rf_raddr_b_o=IO(Output(UInt(5.W)))
  val rf_waddr_wb_o=IO(Output(UInt(5.W))); val rf_we_wb_o=IO(Output(Bool()))
  val rf_wdata_wb_ecc_o=IO(Output(UInt(32.W)))
  val rf_rdata_a_ecc_i=IO(Input(UInt(32.W))); val rf_rdata_b_ecc_i=IO(Input(UInt(32.W)))
  val ic_tag_req_o=IO(Output(UInt(2.W))); val ic_tag_write_o=IO(Output(Bool()))
  val ic_tag_addr_o=IO(Output(UInt(8.W))); val ic_tag_wdata_o=IO(Output(UInt(22.W)))
  val ic_tag_rdata_i=IO(Input(UInt(44.W)))
  val ic_data_req_o=IO(Output(UInt(2.W))); val ic_data_write_o=IO(Output(Bool()))
  val ic_data_addr_o=IO(Output(UInt(8.W))); val ic_data_wdata_o=IO(Output(UInt(64.W)))
  val ic_data_rdata_i=IO(Input(UInt(128.W)))
  val ic_scr_key_valid_i=IO(Input(Bool())); val ic_scr_key_req_o=IO(Output(Bool()))
  val irq_software_i=IO(Input(Bool())); val irq_timer_i=IO(Input(Bool()))
  val irq_external_i=IO(Input(Bool())); val irq_fast_i=IO(Input(UInt(15.W)))
  val irq_nm_i=IO(Input(Bool())); val irq_pending_o=IO(Output(Bool()))
  val debug_req_i=IO(Input(Bool())); val crash_dump_o=IO(Output(UInt(160.W)))
  val double_fault_seen_o=IO(Output(Bool()))
  val fetch_enable_i=IO(Input(UInt(4.W)))
  val alert_minor_o=IO(Output(Bool())); val alert_major_internal_o=IO(Output(Bool()))
  val alert_major_bus_o=IO(Output(Bool())); val core_busy_o=IO(Output(UInt(4.W)))
  if(RegisteredExecution || WithF) {
    // Retain the fixed core interface in both top specialization and standalone
    // instrumentation, so production binding does not discard any ports.
    Seq(ic_data_write_o,dummy_instr_id_o,dummy_instr_wb_o,ic_tag_wdata_o,ic_scr_key_valid_i,
      ic_data_rdata_i,alert_major_internal_o,ic_tag_addr_o,ic_tag_rdata_i,alert_major_bus_o,
      ic_tag_req_o,ic_scr_key_req_o,ic_data_addr_o,ic_data_req_o,alert_minor_o,ic_data_wdata_o,
      ic_tag_write_o).foreach(dontTouch(_))
  }

  // These ports mirror the reference RVFI define. Disable only for physical
  // measurement of the production datapath, never for retirement checking.
  private def trace[T <: Data](gen: T): T = if(WithRVFI) IO(Output(gen)) else Wire(gen)
  val rvfi_valid=trace(Bool()); val rvfi_order=trace(UInt(64.W)); val rvfi_insn=trace(UInt(32.W))
  val rvfi_trap=trace(Bool()); val rvfi_halt=trace(Bool()); val rvfi_intr=trace(Bool())
  val rvfi_mode=trace(UInt(2.W)); val rvfi_ixl=trace(UInt(2.W))
  val rvfi_rs1_addr=trace(UInt(5.W)); val rvfi_rs2_addr=trace(UInt(5.W)); val rvfi_rs3_addr=trace(UInt(5.W))
  val rvfi_rs1_rdata=trace(UInt(32.W)); val rvfi_rs2_rdata=trace(UInt(32.W)); val rvfi_rs3_rdata=trace(UInt(32.W))
  val rvfi_rd_addr=trace(UInt(5.W)); val rvfi_rd_wdata=trace(UInt(32.W))
  val rvfi_pc_rdata=trace(UInt(32.W)); val rvfi_pc_wdata=trace(UInt(32.W))
  val rvfi_mem_addr=trace(UInt(32.W)); val rvfi_mem_rmask=trace(UInt(4.W)); val rvfi_mem_wmask=trace(UInt(4.W))
  val rvfi_mem_rdata=trace(UInt(32.W)); val rvfi_mem_wdata=trace(UInt(32.W))
  val rvfi_ext_pre_mip=trace(UInt(32.W)); val rvfi_ext_post_mip=trace(UInt(32.W))
  val rvfi_ext_nmi=trace(Bool()); val rvfi_ext_nmi_int=trace(Bool())
  val rvfi_ext_debug_req=trace(Bool()); val rvfi_ext_debug_mode=trace(Bool())
  val rvfi_ext_rf_wr_suppress=trace(Bool()); val rvfi_ext_mcycle=trace(UInt(64.W))
  val rvfi_ext_mhpmcounters=trace(UInt(320.W)); val rvfi_ext_mhpmcountersh=trace(UInt(320.W))
  val rvfi_ext_ic_scr_key_valid=trace(Bool()); val rvfi_ext_irq_valid=trace(Bool())

  val rvfi_frs1_addr=if(WithF) Some(trace(UInt(5.W))) else None
  val rvfi_frs2_addr=if(WithF) Some(trace(UInt(5.W))) else None
  val rvfi_frs3_addr=if(WithF) Some(trace(UInt(5.W))) else None
  val rvfi_frs1_rdata=if(WithF) Some(trace(UInt(32.W))) else None
  val rvfi_frs2_rdata=if(WithF) Some(trace(UInt(32.W))) else None
  val rvfi_frs3_rdata=if(WithF) Some(trace(UInt(32.W))) else None
  val rvfi_frs_en=if(WithF) Some(trace(UInt(3.W))) else None
  val rvfi_frd_addr=if(WithF) Some(trace(UInt(5.W))) else None
  val rvfi_frd_wdata=if(WithF) Some(trace(UInt(32.W))) else None
  val rvfi_frd_wen=if(WithF) Some(trace(Bool())) else None
  val rvfi_ext_fcsr=if(WithF) Some(trace(UInt(8.W))) else None
  val rvfi_ext_fs=if(WithF) Some(trace(UInt(2.W))) else None
  val rvfi_ext_fregs=if(WithF) Some(trace(UInt(1024.W))) else None

  val if_stage_i=Module(new IbexIfStage(DmHaltAddr,DmExceptionAddr,RegisteredRedirect=RegisteredExecution,WithF=WithF))
  val id_stage_i=Module(new IbexIdStage(RegisteredExecution=RegisteredExecution,WithF=WithF))
  val ex_block_i=Module(new IbexExBlock(RegisteredExecution=RegisteredExecution))
  val load_store_unit_i=Module(new IbexLoadStoreUnit)
  val wb_stage_i=Module(new IbexWbStage)
  val cs_registers_i=Module(new IbexCsRegisters(DbgTriggerEn,WithF=WithF))
  private val fetch=if_stage_i; private val id=id_stage_i; private val ex=ex_block_i
  private val lsu=load_store_unit_i; private val wb=wb_stage_i; private val csr=cs_registers_i
  val floatDecoded=if(WithF) Some(withClockAndReset(clk_i,(!rst_ni).asAsyncReset) {
    // Decode is qualified to this ID instruction. Clear on every completion or
    // squash, so stale F controls cannot redirect the next integer/CSR decode.
    // The existing ID operand/decode stages settle this register and the FP
    // operand registers before the first execution request is accepted.
    val decoded=FloatInstruction(fetch.instr_rdata_id_o,csr.fp_fcsr_o.get(7,5),csr.fp_fs_o.get,
      directIntegerRead= !RegisteredExecution)
    val selected=WireDefault(decoded)
    // Register the instruction selection too: a legal-F mux after this stage
    // would put its fanout and the full integer decoder on the RF write path.
    // In the faithful path opcode recognition selects the integer-shaped
    // encoding; full F legality qualifies effects in ID, not this wide mux.
    selected.substitute:=Mux(if(RegisteredExecution) decoded.legal else decoded.recognized,
      decoded.substitute,fetch.instr_rdata_id_o)
    if(RegisteredExecution) {
      val metadata=RegNext(selected,0.U.asTypeOf(new FloatDecoded))
      val qualified=RegNext(fetch.instr_valid_id_o,false.B)
      when(id.instr_valid_clear_o) { qualified:=false.B }
      val current=WireDefault(metadata)
      current.recognized:=qualified && metadata.recognized
      current.legal:=qualified && metadata.legal
      current
    } else selected
  }) else None
  val floatExecution=if(WithF) Some(withClockAndReset(clk_i,(!rst_ni).asAsyncReset) {
    Module(new FloatExecution)
  }) else None
  val floatArithmetic=if(WithF) floatDecoded.get.legal && floatDecoded.get.arithmetic else false.B
  val floatLoad=if(WithF) floatDecoded.get.legal && floatDecoded.get.load else false.B
  val floatStore=if(WithF) floatDecoded.get.legal && floatDecoded.get.store else false.B
  if(WithF) {
    val fp=floatExecution.get; val d=floatDecoded.get
    id.fp_instr_i.get:=d.substitute
    id.fp_illegal_i.get:=d.recognized && !d.legal
    if(!RegisteredExecution) {
      id.fp_arithmetic_i.get:=floatArithmetic
      id.fp_prepare_i.get:=floatArithmetic || floatStore
    }
    fp.io.decoded:=d; fp.io.integerOperand:=rf_rdata_a_ecc_i
    fp.io.request:=id.execute_req_o.get && floatArithmetic
    // Legal FP arithmetic is one execute phase; use its accepted response
    // directly, as CSR commit does, without the unrelated LSU/branch-done tree.
    fp.io.commitArithmetic:=id.execute_consume_o.get && floatArithmetic
    fp.io.commitLoad:=id.fp_load_commit_o.get && floatLoad && lsu.lsu_rdata_valid_o &&
      !lsu.load_err_o && !lsu.load_resp_intg_err_o
    fp.io.loadData:=lsu.lsu_rdata_o
    fp.io.cancel:=id.instr_valid_clear_o && !id.instr_id_done_o
    csr.fp_commit_i.get:=fp.io.commitArithmetic || fp.io.commitLoad
    csr.fp_flags_i.get:=Mux(fp.io.commitArithmetic,fp.io.flags,0.U)
    csr.fp_dirty_i.get:=fp.io.commitLoad || (fp.io.commitArithmetic && d.writeFloat)
  }
  fetch.clk_i:=clk_i; fetch.rst_ni:=rst_ni; id.clk_i:=clk_i; id.rst_ni:=rst_ni
  ex.clk_i:=clk_i; ex.rst_ni:=rst_ni; lsu.clk_i:=clk_i; lsu.rst_ni:=rst_ni
  wb.clk_i:=clk_i; wb.rst_ni:=rst_ni; csr.clk_i:=clk_i; csr.rst_ni:=rst_ni

  fetch.boot_addr_i:=boot_addr_i; fetch.req_i:=id.instr_req_o && fetch_enable_i(0)
  instr_req_o:=fetch.instr_req_o; instr_addr_o:=fetch.instr_addr_o
  fetch.instr_gnt_i:=instr_gnt_i; fetch.instr_rvalid_i:=instr_rvalid_i
  fetch.instr_rdata_i:=instr_rdata_i; fetch.instr_bus_err_i:=instr_err_i
  ic_tag_req_o:=fetch.ic_tag_req_o; ic_tag_write_o:=fetch.ic_tag_write_o
  ic_tag_addr_o:=fetch.ic_tag_addr_o; ic_tag_wdata_o:=fetch.ic_tag_wdata_o
  fetch.ic_tag_rdata_i:=ic_tag_rdata_i
  ic_data_req_o:=fetch.ic_data_req_o; ic_data_write_o:=fetch.ic_data_write_o
  ic_data_addr_o:=fetch.ic_data_addr_o; ic_data_wdata_o:=fetch.ic_data_wdata_o
  fetch.ic_data_rdata_i:=ic_data_rdata_i; fetch.ic_scr_key_valid_i:=ic_scr_key_valid_i
  ic_scr_key_req_o:=fetch.ic_scr_key_req_o
  fetch.pmp_err_if_i:=false.B; fetch.pmp_err_if_plus2_i:=false.B
  fetch.instr_valid_clear_i:=id.instr_valid_clear_o; fetch.pc_set_i:=id.pc_set_o
  fetch.pc_mux_i:=id.pc_mux_o; fetch.nt_branch_mispredict_i:=id.nt_branch_mispredict_o
  fetch.nt_branch_addr_i:=id.nt_branch_addr_o; fetch.exc_pc_mux_i:=id.exc_pc_mux_o
  fetch.exc_cause:=id.exc_cause_o; fetch.dummy_instr_en_i:=csr.dummy_instr_en_o
  fetch.dummy_instr_mask_i:=csr.dummy_instr_mask_o; fetch.dummy_instr_seed_en_i:=csr.dummy_instr_seed_en_o
  fetch.dummy_instr_seed_i:=csr.dummy_instr_seed_o; fetch.icache_enable_i:=csr.icache_enable_o
  fetch.icache_inval_i:=id.icache_inval_o; fetch.branch_target_ex_i:=ex.branch_target_o
  fetch.csr_mepc_i:=csr.csr_mepc_o; fetch.csr_depc_i:=csr.csr_depc_o
  fetch.csr_mtvec_i:=csr.csr_mtvec_o; fetch.id_in_ready_i:=id.id_in_ready_o

  id.instr_valid_i:=fetch.instr_valid_id_o; id.instr_rdata_i:=fetch.instr_rdata_id_o
  id.instr_rdata_alu_i:=fetch.instr_rdata_alu_id_o; id.instr_rdata_c_i:=fetch.instr_rdata_c_id_o
  id.instr_is_compressed_i:=fetch.instr_is_compressed_id_o; id.instr_bp_taken_i:=fetch.instr_bp_taken_o
  id.instr_exec_i:=fetch_enable_i(0); id.branch_decision_i:=ex.branch_decision_o
  id.illegal_c_insn_i:=fetch.illegal_c_insn_id_o; id.instr_fetch_err_i:=fetch.instr_fetch_err_o
  id.instr_fetch_err_plus2_i:=fetch.instr_fetch_err_plus2_o; id.pc_id_i:=fetch.pc_id_o
  val executionValid=if(WithF && RegisteredExecution) withClockAndReset(clk_i,(!rst_ni).asAsyncReset) {
    // The new F/integer completion selector is a registered boundary. Both
    // producers hold their response and payload until the qualified consume.
    val valid=RegNext(Mux(floatArithmetic,floatExecution.get.io.valid,ex.ex_valid_o),false.B)
    when(id.execute_consume_o.get || id.instr_valid_clear_o) { valid:=false.B }
    valid
  } else if(WithF) Mux(floatArithmetic,floatExecution.get.io.valid,ex.ex_valid_o) else ex.ex_valid_o
  id.ex_valid_i:=executionValid; id.lsu_resp_valid_i:=lsu.lsu_resp_valid_o
  id.imd_val_we_ex_i:=ex.imd_val_we_o; id.imd_val_d_ex_i:=ex.imd_val_d_o
  id.priv_mode_i:=csr.priv_mode_id_o; id.csr_mstatus_tw_i:=csr.csr_mstatus_tw_o
  id.illegal_csr_insn_i:=csr.illegal_csr_insn_o; id.data_ind_timing_i:=csr.data_ind_timing_o
  id.lsu_req_done_i:=lsu.lsu_req_done_o; id.lsu_addr_incr_req_i:=lsu.addr_incr_req_o
  id.lsu_addr_last_i:=lsu.addr_last_o; id.csr_mstatus_mie_i:=csr.csr_mstatus_mie_o
  id.irq_pending_i:=csr.irq_pending_o; id.irqs_i:=csr.irqs_o; id.irq_nm_i:=irq_nm_i
  id.lsu_load_err_i:=lsu.load_err_o; id.lsu_load_resp_intg_err_i:=lsu.load_resp_intg_err_o
  id.lsu_store_err_i:=lsu.store_err_o; id.lsu_store_resp_intg_err_i:=lsu.store_resp_intg_err_o
  id.debug_req_i:=debug_req_i; id.debug_single_step_i:=csr.debug_single_step_o
  id.debug_ebreakm_i:=csr.debug_ebreakm_o; id.debug_ebreaku_i:=csr.debug_ebreaku_o
  id.trigger_match_i:=csr.trigger_match_o; id.result_ex_i:=(if(WithF) Mux(floatArithmetic,floatExecution.get.io.result,ex.result_ex_o) else ex.result_ex_o); id.csr_rdata_i:=csr.csr_rdata_o
  id.rf_rdata_a_i:=rf_rdata_a_ecc_i; id.rf_rdata_b_i:=(if(WithF) Mux(floatStore,floatExecution.get.io.source2,rf_rdata_b_ecc_i) else rf_rdata_b_ecc_i)
  id.rf_waddr_wb_i:=wb.rf_waddr_wb_o; id.rf_wdata_fwd_wb_i:=wb.rf_wdata_fwd_wb_o
  id.rf_write_wb_i:=wb.rf_write_wb_o; id.ready_wb_i:=wb.ready_wb_o
  id.outstanding_load_wb_i:=wb.outstanding_load_wb_o; id.outstanding_store_wb_i:=wb.outstanding_store_wb_o

  ex.alu_operator_i:=id.alu_operator_ex_o; ex.alu_operand_a_i:=id.alu_operand_a_ex_o
  ex.alu_operand_b_i:=id.alu_operand_b_ex_o; ex.alu_instr_first_cycle_i:=id.instr_first_cycle_id_o
  ex.bt_a_operand_i:=id.bt_a_operand_o; ex.bt_b_operand_i:=id.bt_b_operand_o
  ex.multdiv_operator_i:=id.multdiv_operator_ex_o; ex.mult_en_i:=id.mult_en_ex_o
  ex.div_en_i:=id.div_en_ex_o; ex.mult_sel_i:=id.mult_sel_ex_o; ex.div_sel_i:=id.div_sel_ex_o
  ex.multdiv_signed_mode_i:=id.multdiv_signed_mode_ex_o
  ex.multdiv_operand_a_i:=id.multdiv_operand_a_ex_o; ex.multdiv_operand_b_i:=id.multdiv_operand_b_ex_o
  ex.multdiv_ready_id_i:=id.multdiv_ready_id_o; ex.data_ind_timing_i:=csr.data_ind_timing_o
  ex.imd_val_q_i:=id.imd_val_q_ex_o
  if(RegisteredExecution) {
    ex.execute_req_i.get:=id.execute_req_o.get && !floatArithmetic
    ex.execute_consume_i.get:=id.execute_consume_o.get && !floatArithmetic
  }

  // The F-enabled integration hardens the inherited LSU's bus contract:
  // a response belongs to an earlier granted beat, never an idle/new request.
  // Split accesses can have two grants outstanding; a concurrent old response
  // and new grant exchange ownership without changing the count. Reset alone
  // discards ownership: cancellation cannot retract a grant already on the bus.
  val ownedDataResponse=if(WithF) withClockAndReset(clk_i,(!rst_ni).asAsyncReset) {
    val outstanding=RegInit(0.U(2.W))
    val granted=lsu.data_req_o && data_gnt_i
    val returned=data_rvalid_i && outstanding=/=0.U
    when(granted && !returned) { outstanding:=outstanding+1.U }
      .elsewhen(returned && !granted) { outstanding:=outstanding-1.U }
    returned
  } else data_rvalid_i
  data_req_o:=lsu.data_req_o; lsu.data_gnt_i:=data_gnt_i; lsu.data_rvalid_i:=ownedDataResponse
  lsu.data_bus_err_i:=(if(WithF) data_err_i && ownedDataResponse else data_err_i)
  lsu.data_pmp_err_i:=false.B
  data_addr_o:=lsu.data_addr_o; data_we_o:=lsu.data_we_o; data_be_o:=lsu.data_be_o
  data_wdata_o:=lsu.data_wdata_o; lsu.data_rdata_i:=data_rdata_i
  lsu.lsu_we_i:=id.lsu_we_o; lsu.lsu_type_i:=id.lsu_type_o; lsu.lsu_wdata_i:=id.lsu_wdata_o
  lsu.lsu_sign_ext_i:=id.lsu_sign_ext_o; lsu.lsu_req_i:=id.lsu_req_o
  if(RegisteredExecution) {
    // Fixed +4 split-access address: parallel local increments avoid putting
    // the entire 30-bit carry chain on the LSU's state-to-state path.
    val chunks=(2 until 32 by 4).map { low=>
      val high=math.min(low+3,31)
      val word=lsu.addr_last_o(high,low)
      val incremented=WireDefault(word+1.U((high-low+1).W))
      val carry=WireDefault(if(low==2) true.B else lsu.addr_last_o(low-1,2).andR)
      addAttribute(incremented,"keep = 1"); addAttribute(carry,"keep = 1")
      Mux(carry,incremented,word)
    }
    val splitAddress=Cat(Cat(chunks.reverse),lsu.addr_last_o(1,0))
    lsu.adder_result_ex_i:=Mux(lsu.addr_incr_req_o,splitAddress,ex.alu_adder_result_ex_o)
  } else { lsu.adder_result_ex_i:=ex.alu_adder_result_ex_o }

  wb.en_wb_i:=id.en_wb_o; wb.instr_type_wb_i:=id.instr_type_wb_o; wb.pc_id_i:=fetch.pc_id_o
  wb.instr_is_compressed_id_i:=fetch.instr_is_compressed_id_o
  wb.instr_perf_count_id_i:=id.instr_perf_count_id_o
  wb.rf_waddr_id_i:=id.rf_waddr_id_o; wb.rf_wdata_id_i:=id.rf_wdata_id_o; wb.rf_we_id_i:=id.rf_we_id_o && !floatLoad
  wb.dummy_instr_id_i:=fetch.dummy_instr_id_o; wb.rf_wdata_lsu_i:=lsu.lsu_rdata_o
  // A memory response belongs only to a qualified outstanding integer load.
  // In particular an unsolicited response during F decode must not write X.
  val integerLoadWrite=lsu.lsu_rdata_valid_o && !floatLoad &&
    (if(WithF) id.expecting_load_resp_o else true.B)
  wb.rf_we_lsu_i:=integerLoadWrite; wb.lsu_resp_valid_i:=lsu.lsu_resp_valid_o
  wb.lsu_resp_err_i:=lsu.load_err_o || lsu.store_err_o
  rf_raddr_a_o:=id.rf_raddr_a_o; rf_raddr_b_o:=id.rf_raddr_b_o; rf_waddr_wb_o:=wb.rf_waddr_wb_o
  rf_we_wb_o:=wb.rf_we_wb_o; rf_wdata_wb_ecc_o:=wb.rf_wdata_wb_o
  dummy_instr_id_o:=fetch.dummy_instr_id_o; dummy_instr_wb_o:=wb.dummy_instr_wb_o

  csr.hart_id_i:=hart_id_i; csr.boot_addr_i:=boot_addr_i; csr.csr_mtvec_init_i:=fetch.csr_mtvec_init_o
  if(RegisteredExecution) {
    withClockAndReset(clk_i,(!rst_ni).asAsyncReset) {
      // ID waits for this request stage before sampling CSR legality. Writes
      // still occur only at the instruction's completion, using stable fields.
      csr.csr_access_i:=RegNext(id.csr_access_o,false.B)
      csr.csr_addr_i:=RegNext(Mux(id.csr_access_o,id.alu_operand_b_ex_o(11,0),0.U),0.U)
      csr.csr_wdata_i:=RegNext(id.alu_operand_a_ex_o,0.U)
      csr.csr_op_i:=RegNext(id.csr_op_o,0.U)
    }
  } else {
    csr.csr_access_i:=id.csr_access_o; csr.csr_addr_i:=Mux(id.csr_access_o,id.alu_operand_b_ex_o(11,0),0.U)
    csr.csr_wdata_i:=id.alu_operand_a_ex_o; csr.csr_op_i:=id.csr_op_o
  }
  csr.csr_op_en_i:=id.csr_op_en_o
  csr.irq_software_i:=irq_software_i; csr.irq_timer_i:=irq_timer_i; csr.irq_external_i:=irq_external_i
  csr.irq_fast_i:=irq_fast_i; csr.nmi_mode_i:=id.nmi_mode_o; irq_pending_o:=csr.irq_pending_o
  csr.debug_mode_i:=id.debug_mode_o; csr.debug_mode_entering_i:=id.debug_mode_entering_o
  csr.debug_cause_i:=id.debug_cause_o; csr.debug_csr_save_i:=id.debug_csr_save_o
  csr.pc_if_i:=fetch.pc_if_o; csr.pc_id_i:=fetch.pc_id_o; csr.pc_wb_i:=wb.pc_wb_o
  csr.ic_scr_key_valid_i:=ic_scr_key_valid_i
  csr.csr_save_if_i:=id.csr_save_if_o; csr.csr_save_id_i:=id.csr_save_id_o; csr.csr_save_wb_i:=id.csr_save_wb_o
  csr.csr_restore_mret_i:=id.csr_restore_mret_id_o; csr.csr_restore_dret_i:=id.csr_restore_dret_id_o
  csr.csr_save_cause_i:=id.csr_save_cause_o; csr.csr_mcause_i:=id.exc_cause_o; csr.csr_mtval_i:=id.csr_mtval_o
  double_fault_seen_o:=csr.double_fault_seen_o
  csr.instr_ret_i:=wb.perf_instr_ret_wb_o; csr.instr_ret_compressed_i:=wb.perf_instr_ret_compressed_wb_o
  csr.instr_ret_spec_i:=wb.perf_instr_ret_wb_spec_o
  csr.instr_ret_compressed_spec_i:=wb.perf_instr_ret_compressed_wb_spec_o
  csr.iside_wait_i:=id.id_in_ready_o && !fetch.instr_valid_id_o
  csr.jump_i:=id.perf_jump_o; csr.branch_i:=id.perf_branch_o; csr.branch_taken_i:=id.perf_tbranch_o
  csr.mem_load_i:=lsu.perf_load_o; csr.mem_store_i:=lsu.perf_store_o; csr.dside_wait_i:=id.perf_dside_wait_o
  csr.mul_wait_i:=id.perf_mul_wait_o; csr.div_wait_i:=id.perf_div_wait_o
  crash_dump_o:=Cat(fetch.pc_id_o,fetch.pc_if_o,lsu.addr_last_o,csr.csr_mepc_o,csr.csr_mtval_o)
  alert_minor_o:=fetch.icache_ecc_error_o
  alert_major_internal_o:=fetch.pc_mismatch_alert_o || csr.csr_shadow_err_o
  alert_major_bus_o:=lsu.load_resp_intg_err_o || lsu.store_resp_intg_err_o || fetch.instr_intg_err_o
  core_busy_o:=Mux(id.ctrl_busy_o || fetch.if_busy_o || lsu.busy_o,5.U,10.U)

  // RVFI observes the same internal nodes as the reference cross-module
  // references. BoringUtils creates observation-only wires, not new state.
  if(WithRVFI) {
    val flushNext=BoringUtils.bore(id.controller_i.rvfi_flush_next)
    val idException=BoringUtils.bore(id.controller_i.id_exception_o)
    val ebreak=BoringUtils.bore(id.decoder_i.ebrk_insn_o)
    val validNext=BoringUtils.bore(fetch.instr_valid_id_d)
    val newNext=BoringUtils.bore(fetch.instr_new_id_d)
    val cycle=BoringUtils.bore(csr.mcycle_counter_i.counter_val_o)
    val ebreakDebug=Mux(csr.priv_mode_id_o===3.U,csr.debug_ebreakm_o,
      Mux(csr.priv_mode_id_o===0.U,csr.debug_ebreaku_o,false.B))
    val rvfi_id_done=id.instr_id_done_o || (flushNext && idException)
    val trap=(idException || lsu.load_err_o || lsu.store_err_o) && !(ebreak && ebreakDebug)
    val mip=Cat(irq_software_i,irq_timer_i,irq_external_i,irq_fast_i)
    def irqWord(value: UInt): UInt = Cat(0.U(1.W),value(14,0),0.U(4.W),value(15),
      0.U(3.W),value(16),0.U(3.W),value(17),0.U(3.W))
    // Fault/ECALL/EBREAK phases do not issue an execution transaction. Preserve
    // their upstream incidental RVFI adder value without changing the memory
    // observation of a real load/store, which uses the actual execution reply.
    val exceptionAdder=if(RegisteredExecution) {
      val observation=Module(new IbexAlu)
      observation.operator_i:=id.alu_operator_ex_o
      observation.operand_a_i:=id.alu_operand_a_ex_o
      observation.operand_b_i:=id.alu_operand_b_ex_o
      observation.instr_first_cycle_i:=id.instr_first_cycle_id_o
      observation.multdiv_sel_i:=false.B
      observation.multdiv_operand_a_i:=0.U; observation.multdiv_operand_b_i:=0.U
      observation.imd_val_q_i:=0.U
      observation.adder_result_o
    } else 0.U(32.W)
    withClockAndReset(clk_i,(!rst_ni).asAsyncReset) {
      // Slang preserves the four fields of irqs_t as distinct state cells.
      // Keep their boundaries so the strict named-state induction matches.
      class Irqs extends Bundle {
        val software=Bool(); val timer=Bool(); val external=Bool(); val fast=UInt(15.W)
      }
      def irqState(name: String): Irqs = RegInit(0.U.asTypeOf(new Irqs)).suggestName(name)
      val rvfi_mem_addr_q=RegInit(0.U(32.W)); val rvfi_mem_wdata_q=RegInit(0.U(32.W))
      val rvfi_mem_rdata_q=RegInit(0.U(32.W))
      // Preserve upstream's incidental first-cycle M-operation adder observation
      // (-rs2), even though it is not a memory access. This is trace-only logic.
      val observedAdder=if(RegisteredExecution) Mux(id.mult_sel_ex_o || id.div_sel_ex_o,
        0.U(32.W)-id.multdiv_operand_b_ex_o,
        Mux(!id.execute_req_o.get,exceptionAdder,ex.alu_adder_result_ex_o)) else ex.alu_adder_result_ex_o
      val memAddr=Mux(id.instr_first_cycle_id_o,observedAdder,rvfi_mem_addr_q)
      val memWrite=Mux(id.instr_first_cycle_id_o,id.lsu_wdata_o,rvfi_mem_wdata_q)
      val memRead=Mux(lsu.lsu_resp_valid_o,lsu.lsu_rdata_o,rvfi_mem_rdata_q)
      rvfi_mem_addr_q:=memAddr; rvfi_mem_wdata_q:=memWrite; rvfi_mem_rdata_q:=memRead
      val rvfi_rs1_data_q=RegInit(0.U(32.W)); val rvfi_rs2_data_q=RegInit(0.U(32.W))
      val rvfi_rs1_addr_q=RegInit(0.U(5.W)); val rvfi_rs2_addr_q=RegInit(0.U(5.W))
      val readIntegerA=id.rf_ren_a_o && (if(WithF && !RegisteredExecution)
        !floatArithmetic || floatDecoded.get.useInteger else true.B)
      val rs1Data=Mux(id.instr_first_cycle_id_o,Mux(readIntegerA,id.multdiv_operand_a_ex_o,0.U),rvfi_rs1_data_q)
      val rs2Data=Mux(id.instr_first_cycle_id_o,Mux(id.rf_ren_b_o && !floatStore,id.multdiv_operand_b_ex_o,0.U),rvfi_rs2_data_q)
      val rs1Addr=Mux(id.instr_first_cycle_id_o,Mux(readIntegerA,id.rf_raddr_a_o,0.U),rvfi_rs1_addr_q)
      val rs2Addr=Mux(id.instr_first_cycle_id_o,Mux(id.rf_ren_b_o && !floatStore,id.rf_raddr_b_o,0.U),rvfi_rs2_addr_q)
      rvfi_rs1_data_q:=rs1Data; rvfi_rs2_data_q:=rs2Data; rvfi_rs1_addr_q:=rs1Addr; rvfi_rs2_addr_q:=rs2Addr
      val rvfi_rd_addr_q=RegInit(0.U(5.W)); val rvfi_rd_wdata_q=RegInit(0.U(32.W))
      val rdWe=wb.rf_we_wb_o || integerLoadWrite
      val rdAddr=Mux(rdWe,wb.rf_waddr_wb_o,Mux(fetch.instr_new_id_o,0.U,rvfi_rd_addr_q))
      val rdWrite=Mux(rdWe,Mux(wb.rf_waddr_wb_o===0.U,0.U,
        Mux(wb.rf_we_wb_o,wb.rf_wdata_wb_o,lsu.lsu_rdata_o)),Mux(fetch.instr_new_id_o,0.U,rvfi_rd_wdata_q))
      rvfi_rd_addr_q:=rdAddr; rvfi_rd_wdata_q:=rdWrite
      val rvfi_set_trap_pc_q=RegInit(false.B); val rvfi_intr_q=RegInit(false.B)
      val intr=Mux(id.instr_first_cycle_id_o,rvfi_set_trap_pc_q,rvfi_intr_q)
      rvfi_intr_q:=intr
      when(id.pc_set_o && id.pc_mux_o===2.U && (id.exc_pc_mux_o===0.U || id.exc_pc_mux_o===1.U)) {
        rvfi_set_trap_pc_q:=true.B
      }.elsewhen(rvfi_set_trap_pc_q && rvfi_id_done) { rvfi_set_trap_pc_q:=false.B }

      val captured_valid=RegInit(false.B); val capturedMip=irqState("captured_mip_fields")
      val captured_mip=capturedMip.asUInt
      val captured_nmi=RegInit(false.B); val captured_nmi_int=dontTouch(RegInit(false.B))
      val captured_debug_req=RegInit(false.B); val rvfi_irq_valid=RegInit(false.B)
      val newDebug=debug_req_i && !id.debug_mode_o
      val newNmi=irq_nm_i && !id.nmi_mode_o && !id.debug_mode_o
      val newIrq=irq_pending_o && (csr.csr_mstatus_mie_o || csr.priv_mode_id_o===0.U) &&
        !id.nmi_mode_o && !id.debug_mode_o
      when(!fetch.instr_valid_id_o && (newDebug || newNmi || newIrq) &&
        (!captured_valid || (newDebug && !captured_debug_req) ||
          (newNmi && !captured_nmi && !captured_debug_req))) {
        captured_valid:=true.B; capturedMip:=mip.asTypeOf(new Irqs); captured_nmi:=irq_nm_i
        captured_nmi_int:=false.B; captured_debug_req:=debug_req_i
      }
      rvfi_irq_valid:= !fetch.instr_valid_id_o && !newDebug && (newIrq || newNmi) &&
        wb.ready_wb_o && !captured_valid
      when(validNext) { captured_valid:=false.B }
      val preMip0=irqState("rvfi_ext_stage_pre_mip_0")
      val nmi0=RegInit(false.B).suggestName("rvfi_ext_stage_nmi_0")
      val nmiInt0=dontTouch(RegInit(false.B)).suggestName("rvfi_ext_stage_nmi_int_0")
      val debugReq0=RegInit(false.B).suggestName("rvfi_ext_stage_debug_req_0")
      when((validNext && newNext) || rvfi_irq_valid) {
        val useCurrent=fetch.instr_valid_id_o || !captured_valid
        preMip0:=Mux(useCurrent,mip,captured_mip).asTypeOf(new Irqs); nmi0:=Mux(useCurrent,irq_nm_i,captured_nmi)
        nmiInt0:=Mux(useCurrent,false.B,captured_nmi_int)
        debugReq0:=Mux(useCurrent,debug_req_i,captured_debug_req)
      }
      val irqValid0=RegNext(rvfi_irq_valid,false.B).suggestName("rvfi_ext_stage_irq_valid_0")
      val irqValid1=RegNext(irqValid0,false.B).suggestName("rvfi_ext_stage_irq_valid_1")
      val rvfi_ext_stage_irq_valid=Cat(irqValid0,irqValid1)
      dontTouch(rvfi_ext_stage_irq_valid)
      rvfi_ext_irq_valid:=irqValid1

      // Reference uses a one-element unpacked stage array in this profile.
      // Explicit names allow its state to be matched without cycle offsets.
      def stage[T <: Data](name: String, value: T, initial: T, enable: Bool=rvfi_id_done): T = {
        val state=dontTouch(RegInit(initial)).suggestName(name)
        when(enable) { state:=value }; state
      }
      val order=RegInit(0.U(64.W)).suggestName("rvfi_stage_order")
      when(rvfi_id_done) { order:=Mux(fetch.dummy_instr_id_o,order,order+1.U) }
      rvfi_order:=order
      rvfi_valid:=stage("rvfi_stage_valid",rvfi_id_done && !fetch.dummy_instr_id_o,false.B,true.B)
      if(WithF) {
        val fp=floatExecution.get; val d=floatDecoded.get
        val enabled=d.legal && !trap
        rvfi_frs_en.get:=stage("rvfi_stage_frs_en",Mux(enabled,Cat(d.useF3,d.useF2,d.useF1),0.U),0.U(3.W))
        rvfi_frs1_addr.get:=stage("rvfi_stage_frs1_addr",d.rs1,0.U(5.W))
        rvfi_frs2_addr.get:=stage("rvfi_stage_frs2_addr",d.rs2,0.U(5.W))
        rvfi_frs3_addr.get:=stage("rvfi_stage_frs3_addr",d.rs3,0.U(5.W))
        rvfi_frs1_rdata.get:=stage("rvfi_stage_frs1_rdata",fp.io.source1,0.U(32.W))
        rvfi_frs2_rdata.get:=stage("rvfi_stage_frs2_rdata",fp.io.source2,0.U(32.W))
        rvfi_frs3_rdata.get:=stage("rvfi_stage_frs3_rdata",fp.io.source3,0.U(32.W))
        rvfi_frd_wen.get:=stage("rvfi_stage_frd_wen",fp.io.write && !trap,false.B)
        rvfi_frd_addr.get:=stage("rvfi_stage_frd_addr",fp.io.writeAddress,0.U(5.W))
        rvfi_frd_wdata.get:=stage("rvfi_stage_frd_wdata",fp.io.writeData,0.U(32.W))
        rvfi_ext_fcsr.get:=csr.fp_fcsr_o.get; rvfi_ext_fs.get:=csr.fp_fs_o.get
        rvfi_ext_fregs.get:=fp.io.registers
      }
      rvfi_halt:=stage("rvfi_stage_halt",false.B,false.B)
      rvfi_trap:=stage("rvfi_stage_trap",trap,false.B)
      rvfi_intr:=stage("rvfi_stage_intr",intr,false.B)
      rvfi_insn:=stage("rvfi_stage_insn",Mux(fetch.instr_is_compressed_id_o,
        Cat(0.U(16.W),fetch.instr_rdata_c_id_o),fetch.instr_rdata_id_o),0.U(32.W))
      rvfi_mode:=stage("rvfi_stage_mode",csr.priv_mode_id_o,3.U(2.W))
      rvfi_ixl:=stage("rvfi_stage_ixl",1.U(2.W),1.U(2.W))
      rvfi_rs1_addr:=stage("rvfi_stage_rs1_addr",rs1Addr,0.U(5.W))
      rvfi_rs2_addr:=stage("rvfi_stage_rs2_addr",rs2Addr,0.U(5.W))
      rvfi_rs3_addr:=stage("rvfi_stage_rs3_addr",Mux(id.instr_first_cycle_id_o,0.U,id.rf_raddr_a_o),0.U(5.W))
      rvfi_rs1_rdata:=stage("rvfi_stage_rs1_rdata",rs1Data,0.U(32.W))
      rvfi_rs2_rdata:=stage("rvfi_stage_rs2_rdata",rs2Data,0.U(32.W))
      rvfi_rs3_rdata:=stage("rvfi_stage_rs3_rdata",Mux(id.instr_first_cycle_id_o,0.U,id.multdiv_operand_a_ex_o),0.U(32.W))
      rvfi_rd_addr:=stage("rvfi_stage_rd_addr",rdAddr,0.U(5.W))
      rvfi_rd_wdata:=stage("rvfi_stage_rd_wdata",rdWrite,0.U(32.W))
      rvfi_pc_rdata:=stage("rvfi_stage_pc_rdata",fetch.pc_id_o,0.U(32.W))
      val observedNextPc=Mux(id.pc_set_o,ex.branch_target_o,fetch.pc_if_o)
      // Returns retire before the controller's redirect phase. Report their
      // architectural target, not the still-sequential prefetch PC.
      val retiredNextPc=if(WithF) Mux(!trap && fetch.instr_rdata_id_o==="h30200073".U,csr.csr_mepc_o,
        Mux(!trap && fetch.instr_rdata_id_o==="h7b200073".U,csr.csr_depc_o,observedNextPc)) else observedNextPc
      rvfi_pc_wdata:=stage("rvfi_stage_pc_wdata",retiredNextPc,0.U(32.W))
      val mask=MuxLookup(id.lsu_type_o,0.U(4.W))(Seq(0.U->15.U(4.W),1.U->3.U(4.W),2.U->1.U(4.W)))
      rvfi_mem_rmask:=stage("rvfi_stage_mem_rmask",mask,0.U(4.W))
      rvfi_mem_wmask:=stage("rvfi_stage_mem_wmask",Mux(data_we_o,mask,0.U),0.U(4.W))
      rvfi_mem_addr:=stage("rvfi_stage_mem_addr",memAddr,0.U(32.W))
      rvfi_mem_rdata:=stage("rvfi_stage_mem_rdata",memRead,0.U(32.W))
      rvfi_mem_wdata:=stage("rvfi_stage_mem_wdata",memWrite,0.U(32.W))
      rvfi_ext_debug_mode:=stage("rvfi_ext_stage_debug_mode",id.debug_mode_o,false.B)
      rvfi_ext_mcycle:=stage("rvfi_ext_stage_mcycle",cycle,0.U(64.W))
      rvfi_ext_ic_scr_key_valid:=stage("rvfi_ext_stage_ic_scr_key_valid",false.B,false.B)
      val hpmLow=(0 until 10).map(i=>stage(s"rvfi_ext_stage_mhpmcounters_$i",0.U(32.W),0.U(32.W)))
      val hpmHigh=(0 until 10).map(i=>stage(s"rvfi_ext_stage_mhpmcountersh_$i",0.U(32.W),0.U(32.W)))
      rvfi_ext_mhpmcounters:=Cat(hpmLow); rvfi_ext_mhpmcountersh:=Cat(hpmHigh); rvfi_ext_rf_wr_suppress:=false.B
      val extEnable=rvfi_id_done || irqValid0
      val preMip1=irqState("rvfi_ext_stage_pre_mip_1")
      val postMip=irqState("rvfi_ext_stage_post_mip_fields")
      when(extEnable) { preMip1:=preMip0; postMip:=mip.asTypeOf(new Irqs) }
      val rvfi_ext_stage_pre_mip=Cat(preMip0.asUInt,preMip1.asUInt)
      val rvfi_ext_stage_post_mip=postMip.asUInt
      dontTouch(rvfi_ext_stage_pre_mip); dontTouch(rvfi_ext_stage_post_mip)
      rvfi_ext_pre_mip:=irqWord(preMip1.asUInt); rvfi_ext_post_mip:=irqWord(postMip.asUInt)
      val nmi1=stage("rvfi_ext_stage_nmi_1",nmi0,false.B,extEnable)
      val nmiInt1=stage("rvfi_ext_stage_nmi_int_1",nmiInt0,false.B,extEnable)
      val debugReq1=stage("rvfi_ext_stage_debug_req_1",debugReq0,false.B,extEnable)
      val rvfi_ext_stage_nmi=Cat(nmi0,nmi1); val rvfi_ext_stage_nmi_int=Cat(nmiInt0,nmiInt1)
      val rvfi_ext_stage_debug_req=Cat(debugReq0,debugReq1)
      dontTouch(rvfi_ext_stage_nmi); dontTouch(rvfi_ext_stage_nmi_int); dontTouch(rvfi_ext_stage_debug_req)
      rvfi_ext_nmi:=nmi1; rvfi_ext_nmi_int:=nmiInt1; rvfi_ext_debug_req:=debugReq1
    }
  } else {
    if(WithF) {
      Seq(rvfi_frs1_addr.get,rvfi_frs2_addr.get,rvfi_frs3_addr.get,
        rvfi_frs1_rdata.get,rvfi_frs2_rdata.get,rvfi_frs3_rdata.get,rvfi_frs_en.get,
        rvfi_frd_addr.get,rvfi_frd_wdata.get,rvfi_ext_fcsr.get,rvfi_ext_fs.get,
        rvfi_ext_fregs.get).foreach(_:=0.U)
      rvfi_frd_wen.get:=false.B
    }
    Seq(rvfi_valid,rvfi_trap,rvfi_halt,rvfi_intr,rvfi_ext_nmi,rvfi_ext_nmi_int,
      rvfi_ext_debug_req,rvfi_ext_debug_mode,rvfi_ext_rf_wr_suppress,rvfi_ext_ic_scr_key_valid,
      rvfi_ext_irq_valid).foreach(_:=false.B)
    Seq(rvfi_order,rvfi_insn,rvfi_mode,rvfi_ixl,rvfi_rs1_addr,rvfi_rs2_addr,rvfi_rs3_addr,
      rvfi_rs1_rdata,rvfi_rs2_rdata,rvfi_rs3_rdata,rvfi_rd_addr,rvfi_rd_wdata,rvfi_pc_rdata,
      rvfi_pc_wdata,rvfi_mem_addr,rvfi_mem_rmask,rvfi_mem_wmask,rvfi_mem_rdata,rvfi_mem_wdata,
      rvfi_ext_pre_mip,rvfi_ext_post_mip,rvfi_ext_mcycle,rvfi_ext_mhpmcounters,rvfi_ext_mhpmcountersh).foreach(_:=0.U)
  }
}
