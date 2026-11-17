// Copyright lowRISC contributors; ETH Zurich and University of Bologna.
// Licensed under Apache-2.0. SPDX-License-Identifier: Apache-2.0
// Translation of rtl/ibex_id_stage.sv, Ibex
// 38c070939183cc10940b66c8e9e04eeca6b65470, pinned two-stage configuration.
package deadhorse.perf_core

import chisel3._
import chisel3.util._

class IbexIdStage(val RV32E: Boolean = false, val RV32M: Int = 2, val RV32B: Int = 0,
    val DataIndTiming: Boolean = false, val BranchTargetALU: Boolean = false,
    val WritebackStage: Boolean = false, val BranchPredictor: Boolean = false,
    val MemECC: Boolean = false, val RegisteredExecution: Boolean = false, val WithF: Boolean = false) extends RawModule {
  require(!RV32E && RV32M==2 && RV32B==0 && !DataIndTiming && !BranchTargetALU &&
    !WritebackStage && !BranchPredictor && !MemECC,"T11 implements the pinned ID stage")
  override def desiredName="ibex_id_stage"
  val clk_i=IO(Input(Clock())); val rst_ni=IO(Input(Bool()))
  val ctrl_busy_o=IO(Output(Bool())); val illegal_insn_o=IO(Output(Bool()))
  val instr_valid_i=IO(Input(Bool())); val instr_rdata_i=IO(Input(UInt(32.W)))
  val instr_rdata_alu_i=IO(Input(UInt(32.W))); val instr_rdata_c_i=IO(Input(UInt(16.W)))
  val instr_is_compressed_i=IO(Input(Bool())); val instr_bp_taken_i=IO(Input(Bool()))
  val instr_req_o=IO(Output(Bool())); val instr_first_cycle_id_o=IO(Output(Bool()))
  val instr_valid_clear_o=IO(Output(Bool())); val id_in_ready_o=IO(Output(Bool()))
  val instr_exec_i=IO(Input(Bool())); val icache_inval_o=IO(Output(Bool()))
  val branch_decision_i=IO(Input(Bool())); val pc_set_o=IO(Output(Bool()))
  val pc_mux_o=IO(Output(UInt(3.W))); val nt_branch_mispredict_o=IO(Output(Bool()))
  val nt_branch_addr_o=IO(Output(UInt(32.W))); val exc_pc_mux_o=IO(Output(UInt(2.W)))
  val exc_cause_o=IO(Output(UInt(7.W))); val illegal_c_insn_i=IO(Input(Bool()))
  val instr_fetch_err_i=IO(Input(Bool())); val instr_fetch_err_plus2_i=IO(Input(Bool()))
  val pc_id_i=IO(Input(UInt(32.W))); val ex_valid_i=IO(Input(Bool())); val lsu_resp_valid_i=IO(Input(Bool()))
  val alu_operator_ex_o=IO(Output(UInt(7.W)))
  val alu_operand_a_ex_o=IO(Output(UInt(32.W))); val alu_operand_b_ex_o=IO(Output(UInt(32.W)))
  val imd_val_we_ex_i=IO(Input(UInt(2.W))); val imd_val_d_ex_i=IO(Input(UInt(68.W)))
  val imd_val_q_ex_o=IO(Output(UInt(68.W)))
  val bt_a_operand_o=IO(Output(UInt(32.W))); val bt_b_operand_o=IO(Output(UInt(32.W)))
  val mult_en_ex_o=IO(Output(Bool())); val div_en_ex_o=IO(Output(Bool()))
  val mult_sel_ex_o=IO(Output(Bool())); val div_sel_ex_o=IO(Output(Bool()))
  val multdiv_operator_ex_o=IO(Output(UInt(2.W))); val multdiv_signed_mode_ex_o=IO(Output(UInt(2.W)))
  val multdiv_operand_a_ex_o=IO(Output(UInt(32.W))); val multdiv_operand_b_ex_o=IO(Output(UInt(32.W)))
  val multdiv_ready_id_o=IO(Output(Bool()))
  val csr_access_o=IO(Output(Bool())); val csr_op_o=IO(Output(UInt(2.W))); val csr_op_en_o=IO(Output(Bool()))
  val csr_save_if_o=IO(Output(Bool())); val csr_save_id_o=IO(Output(Bool())); val csr_save_wb_o=IO(Output(Bool()))
  val csr_restore_mret_id_o=IO(Output(Bool())); val csr_restore_dret_id_o=IO(Output(Bool()))
  val csr_save_cause_o=IO(Output(Bool())); val csr_mtval_o=IO(Output(UInt(32.W)))
  val priv_mode_i=IO(Input(UInt(2.W))); val csr_mstatus_tw_i=IO(Input(Bool()))
  val illegal_csr_insn_i=IO(Input(Bool())); val data_ind_timing_i=IO(Input(Bool()))
  val lsu_req_o=IO(Output(Bool())); val lsu_we_o=IO(Output(Bool()))
  val lsu_type_o=IO(Output(UInt(2.W))); val lsu_sign_ext_o=IO(Output(Bool())); val lsu_wdata_o=IO(Output(UInt(32.W)))
  val lsu_req_done_i=IO(Input(Bool())); val lsu_addr_incr_req_i=IO(Input(Bool())); val lsu_addr_last_i=IO(Input(UInt(32.W)))
  val csr_mstatus_mie_i=IO(Input(Bool())); val irq_pending_i=IO(Input(Bool())); val irqs_i=IO(Input(UInt(18.W)))
  val irq_nm_i=IO(Input(Bool())); val nmi_mode_o=IO(Output(Bool()))
  val lsu_load_err_i=IO(Input(Bool())); val lsu_load_resp_intg_err_i=IO(Input(Bool()))
  val lsu_store_err_i=IO(Input(Bool())); val lsu_store_resp_intg_err_i=IO(Input(Bool()))
  val expecting_load_resp_o=IO(Output(Bool())); val expecting_store_resp_o=IO(Output(Bool()))
  val debug_mode_o=IO(Output(Bool())); val debug_mode_entering_o=IO(Output(Bool()))
  val debug_cause_o=IO(Output(UInt(3.W))); val debug_csr_save_o=IO(Output(Bool()))
  val debug_req_i=IO(Input(Bool())); val debug_single_step_i=IO(Input(Bool()))
  val debug_ebreakm_i=IO(Input(Bool())); val debug_ebreaku_i=IO(Input(Bool())); val trigger_match_i=IO(Input(Bool()))
  val result_ex_i=IO(Input(UInt(32.W))); val csr_rdata_i=IO(Input(UInt(32.W)))
  val rf_raddr_a_o=IO(Output(UInt(5.W))); val rf_rdata_a_i=IO(Input(UInt(32.W)))
  val rf_raddr_b_o=IO(Output(UInt(5.W))); val rf_rdata_b_i=IO(Input(UInt(32.W)))
  val rf_ren_a_o=IO(Output(Bool())); val rf_ren_b_o=IO(Output(Bool()))
  val rf_waddr_id_o=IO(Output(UInt(5.W))); val rf_wdata_id_o=IO(Output(UInt(32.W))); val rf_we_id_o=IO(Output(Bool()))
  val rf_rd_a_wb_match_o=IO(Output(Bool())); val rf_rd_b_wb_match_o=IO(Output(Bool()))
  val rf_waddr_wb_i=IO(Input(UInt(5.W))); val rf_wdata_fwd_wb_i=IO(Input(UInt(32.W))); val rf_write_wb_i=IO(Input(Bool()))
  val en_wb_o=IO(Output(Bool())); val instr_type_wb_o=IO(Output(UInt(2.W))); val instr_perf_count_id_o=IO(Output(Bool()))
  val ready_wb_i=IO(Input(Bool())); val outstanding_load_wb_i=IO(Input(Bool())); val outstanding_store_wb_i=IO(Input(Bool()))
  val perf_jump_o=IO(Output(Bool())); val perf_branch_o=IO(Output(Bool())); val perf_tbranch_o=IO(Output(Bool()))
  val perf_dside_wait_o=IO(Output(Bool())); val perf_mul_wait_o=IO(Output(Bool())); val perf_div_wait_o=IO(Output(Bool()))
  val instr_id_done_o=IO(Output(Bool()))
  val execute_req_o=if(RegisteredExecution || WithF) Some(IO(Output(Bool()))) else None
  val execute_consume_o=if(RegisteredExecution || WithF) Some(IO(Output(Bool()))) else None
  val fp_arithmetic_i=if(WithF && !RegisteredExecution) Some(IO(Input(Bool()))) else None
  val fp_prepare_i=if(WithF && !RegisteredExecution) Some(IO(Input(Bool()))) else None
  val fp_instr_i=if(WithF) Some(IO(Input(UInt(32.W)))) else None
  val fp_illegal_i=if(WithF) Some(IO(Input(Bool()))) else None
  val fp_load_commit_o=if(WithF) Some(IO(Output(Bool()))) else None
  val executionPhaseReady=WireDefault(true.B)

  val decoder_i=Module(new IbexDecoder(RV32E,RV32M,RV32B,BranchTargetALU))
  val controller_i=Module(new IbexController(WritebackStage,BranchPredictor,MemECC,RegisteredExecution))
  val dec=decoder_i; val ctrl=controller_i
  def stableControl(value:Bool):Bool=if(RegisteredExecution)
    withClockAndReset(clk_i,(!rst_ni).asAsyncReset) { RegNext(value,false.B) } else value
  val fpEffectsAllowed=if(WithF && !RegisteredExecution) !fp_illegal_i.get else true.B
  val dataRequest=stableControl(dec.data_req_o) && fpEffectsAllowed
  val integerWrite=if(WithF) stableControl(dec.rf_we_o) else dec.rf_we_o
  val storeInstruction=if(WithF) stableControl(dec.data_we_o) else dec.data_we_o
  val multiplyEnable=stableControl(dec.mult_en_o); val divideEnable=stableControl(dec.div_en_o)
  val branchInstruction=stableControl(dec.branch_in_dec_o); val jumpInstruction=stableControl(dec.jump_in_dec_o)
  val ecallInstruction=stableControl(dec.ecall_insn_o); val ebreakInstruction=stableControl(dec.ebrk_insn_o)
  val mretInstruction=stableControl(dec.mret_insn_o); val dretInstruction=stableControl(dec.dret_insn_o)
  val wfiInstruction=stableControl(dec.wfi_insn_o)
  val csrInstruction=stableControl(dec.csr_access_o)
  val jumpSet=stableControl(dec.jump_set_o)
  val decodeReady=WireDefault(true.B)
  if(WithF && !RegisteredExecution) {
    withClockAndReset(clk_i,(!rst_ni).asAsyncReset) {
      val fp_operands_ready_q=RegInit(false.B)
      when(instr_valid_i && ctrl.controller_run_o && fp_prepare_i.get) { fp_operands_ready_q:=true.B }
      when(instr_valid_clear_o) { fp_operands_ready_q:=false.B }
      decodeReady:= !fp_prepare_i.get || fp_operands_ready_q
      executionPhaseReady:=decodeReady
    }
  }
  val effectiveIllegalCsr=WireDefault(illegal_csr_insn_i)
  dec.clk_i:=clk_i; dec.rst_ni:=rst_ni; ctrl.clk_i:=clk_i; ctrl.rst_ni:=rst_ni
  dec.instr_rdata_i:=(if(WithF) fp_instr_i.get else instr_rdata_i)
  dec.instr_rdata_alu_i:=(if(WithF) fp_instr_i.get else instr_rdata_alu_i)
  dec.illegal_c_insn_i:=illegal_c_insn_i; dec.branch_taken_i:=true.B
  icache_inval_o:=dec.icache_inval_o; rf_raddr_a_o:=dec.rf_raddr_a_o
  rf_raddr_b_o:=dec.rf_raddr_b_o; rf_waddr_id_o:=dec.rf_waddr_o
  alu_operator_ex_o:=dec.alu_operator_o
  mult_sel_ex_o:=dec.mult_sel_o; div_sel_ex_o:=dec.div_sel_o
  multdiv_operator_ex_o:=dec.multdiv_operator_o; multdiv_signed_mode_ex_o:=dec.multdiv_signed_mode_o
  csr_access_o:=dec.csr_access_o; csr_op_o:=dec.csr_op_o
  lsu_we_o:=storeInstruction; lsu_type_o:=dec.data_type_o; lsu_sign_ext_o:=dec.data_sign_extension_o
  lsu_wdata_o:=rf_rdata_b_i
  multdiv_operand_a_ex_o:=rf_rdata_a_i; multdiv_operand_b_ex_o:=rf_rdata_b_i
  multdiv_ready_id_o:=ready_wb_i
  bt_a_operand_o:=0.U; bt_b_operand_o:=0.U; nt_branch_addr_o:=0.U
  rf_rd_a_wb_match_o:=false.B; rf_rd_b_wb_match_o:=false.B; instr_type_wb_o:=2.U
  rf_wdata_id_o:=Mux(dec.rf_wdata_sel_o===1.U,csr_rdata_i,result_ex_i)
  val illegal_dret=dec.dret_insn_o && !ctrl.debug_mode_o
  val illegal_umode=priv_mode_i=/=3.U && (dec.mret_insn_o || (csr_mstatus_tw_i && dec.wfi_insn_o))
  val currentCsrIllegal=if(WithF) dec.csr_access_o && illegal_csr_insn_i else illegal_csr_insn_i
  val decodedIllegal=dec.illegal_insn_o || currentCsrIllegal || illegal_dret || illegal_umode || (if(WithF) fp_illegal_i.get else false.B)
  if(RegisteredExecution) {
    // Break the instruction -> CSR legality -> controller -> fetch-ready path.
    // No execution request or instruction effect is allowed before this stage.
    withClockAndReset(clk_i,(!rst_ni).asAsyncReset) {
      val decoded_q=RegInit(false.B)
      val operands_staged_q=RegInit(false.B)
      // With F, instruction selection precedes decode. CSR legality also
      // traverses the core CSR request register and needs one further cycle.
      val csr_request_staged_q=if(WithF) Some(RegInit(false.B)) else None
      val illegal_q=RegInit(false.B)
      val illegal_csr_q=RegInit(false.B)
      when(instr_valid_i && ctrl.controller_run_o && !decoded_q) {
        operands_staged_q:=true.B
        if(WithF) { csr_request_staged_q.get:=operands_staged_q }
        val settled=if(WithF) !dec.csr_access_o || csr_request_staged_q.get else true.B
        when(operands_staged_q && settled) {
          decoded_q:=true.B; illegal_q:=decodedIllegal; illegal_csr_q:=currentCsrIllegal
        }
      }
      when(instr_valid_clear_o) {
        decoded_q:=false.B; operands_staged_q:=false.B
        if(WithF) { csr_request_staged_q.get:=false.B }
      }
      decodeReady:=decoded_q
      illegal_insn_o:=instr_valid_i && decoded_q && illegal_q
      effectiveIllegalCsr:=illegal_csr_q
    }
  } else { illegal_insn_o:=instr_valid_i && decodedIllegal }
  rf_ren_a_o:=instr_valid_i && !instr_fetch_err_i && !illegal_insn_o && dec.rf_ren_a_o
  rf_ren_b_o:=instr_valid_i && !instr_fetch_err_i && !illegal_insn_o && dec.rf_ren_b_o
  val opA=Mux(lsu_addr_incr_req_i,1.U,dec.alu_op_a_mux_sel_o)
  val opB=Mux(lsu_addr_incr_req_i,1.U,dec.alu_op_b_mux_sel_o)
  val immBSelect=Mux(lsu_addr_incr_req_i,6.U,dec.imm_b_mux_sel_o)
  val immA=Mux(dec.imm_a_mux_sel_o===0.U,dec.zimm_rs1_type_o,0.U)
  alu_operand_a_ex_o:=MuxLookup(opA,pc_id_i)(Seq(0.U->rf_rdata_a_i,1.U->lsu_addr_last_i,2.U->pc_id_i,3.U->immA))
  val immB=MuxLookup(immBSelect,4.U(32.W))(Seq(0.U->dec.imm_i_type_o,1.U->dec.imm_s_type_o,
    2.U->dec.imm_b_type_o,3.U->dec.imm_u_type_o,4.U->dec.imm_j_type_o,
    5.U->Mux(instr_is_compressed_i,2.U(32.W),4.U(32.W)),6.U->4.U(32.W)))
  alu_operand_b_ex_o:=Mux(opB===1.U,immB,rf_rdata_b_i)
  val csr_flush_decode=WireDefault(false.B)
  when(csr_op_o===1.U || csr_op_o===2.U) {
    csr_flush_decode:=instr_rdata_i(31,20)==="h300".U || instr_rdata_i(31,20)==="h304".U ||
      instr_rdata_i(31,20)==="h747".U || instr_rdata_i(31,25)==="h1d".U
  }.elsewhen(csr_op_o=/=0.U) {
    csr_flush_decode:=instr_rdata_i(31,20)>="h7b0".U && instr_rdata_i(31,20)<="h7b3".U
  }
  val csr_pipe_flush=csr_op_en_o && stableControl(csr_flush_decode)
  ctrl.illegal_insn_i:=illegal_insn_o; ctrl.ecall_insn_i:=ecallInstruction
  ctrl.mret_insn_i:=mretInstruction; ctrl.dret_insn_i:=dretInstruction
  ctrl.wfi_insn_i:=wfiInstruction
  if(RegisteredExecution) ctrl.execute_phase_ready_i.get:=executionPhaseReady
  ctrl.ebrk_insn_i:=ebreakInstruction; ctrl.csr_pipe_flush_i:=csr_pipe_flush
  ctrl.instr_valid_i:=instr_valid_i; ctrl.instr_i:=instr_rdata_i; ctrl.instr_compressed_i:=instr_rdata_c_i
  ctrl.instr_is_compressed_i:=instr_is_compressed_i; ctrl.instr_bp_taken_i:=instr_bp_taken_i
  ctrl.instr_fetch_err_i:=instr_fetch_err_i; ctrl.instr_fetch_err_plus2_i:=instr_fetch_err_plus2_i
  ctrl.pc_id_i:=pc_id_i; ctrl.instr_exec_i:=instr_exec_i
  ctrl.lsu_addr_last_i:=lsu_addr_last_i; ctrl.load_err_i:=lsu_load_err_i; ctrl.store_err_i:=lsu_store_err_i
  ctrl.mem_resp_intg_err_i:=lsu_load_resp_intg_err_i || lsu_store_resp_intg_err_i
  ctrl.csr_mstatus_mie_i:=csr_mstatus_mie_i; ctrl.irq_pending_i:=irq_pending_i; ctrl.irqs_i:=irqs_i
  ctrl.irq_nm_ext_i:=irq_nm_i; ctrl.priv_mode_i:=priv_mode_i
  ctrl.debug_req_i:=debug_req_i; ctrl.debug_single_step_i:=debug_single_step_i
  ctrl.debug_ebreakm_i:=debug_ebreakm_i; ctrl.debug_ebreaku_i:=debug_ebreaku_i; ctrl.trigger_match_i:=trigger_match_i
  ctrl.stall_wb_i:=false.B; ctrl.ready_wb_i:=ready_wb_i; ctrl.branch_not_set_i:=false.B
  ctrl_busy_o:=ctrl.ctrl_busy_o; instr_valid_clear_o:=ctrl.instr_valid_clear_o
  id_in_ready_o:=ctrl.id_in_ready_o; instr_req_o:=ctrl.instr_req_o; pc_set_o:=ctrl.pc_set_o
  pc_mux_o:=ctrl.pc_mux_o; nt_branch_mispredict_o:=ctrl.nt_branch_mispredict_o
  exc_pc_mux_o:=ctrl.exc_pc_mux_o; exc_cause_o:=ctrl.exc_cause_o; nmi_mode_o:=ctrl.nmi_mode_o
  csr_save_if_o:=ctrl.csr_save_if_o; csr_save_id_o:=ctrl.csr_save_id_o; csr_save_wb_o:=ctrl.csr_save_wb_o
  csr_restore_mret_id_o:=ctrl.csr_restore_mret_id_o; csr_restore_dret_id_o:=ctrl.csr_restore_dret_id_o
  csr_save_cause_o:=ctrl.csr_save_cause_o; csr_mtval_o:=ctrl.csr_mtval_o
  debug_mode_o:=ctrl.debug_mode_o; debug_mode_entering_o:=ctrl.debug_mode_entering_o
  debug_cause_o:=ctrl.debug_cause_o; debug_csr_save_o:=ctrl.debug_csr_save_o
  perf_jump_o:=ctrl.perf_jump_o; perf_tbranch_o:=ctrl.perf_tbranch_o

  withClockAndReset(clk_i,(!rst_ni).asAsyncReset) {
    val imd_val_q_0=RegInit(0.U(34.W)); val imd_val_q_1=RegInit(0.U(34.W))
    when(imd_val_we_ex_i(0)) { imd_val_q_0:=imd_val_d_ex_i(67,34) }
    when(imd_val_we_ex_i(1)) { imd_val_q_1:=imd_val_d_ex_i(33,0) }
    imd_val_q_ex_o:=Cat(imd_val_q_0,imd_val_q_1)
    val id_fsm_q=RegInit(false.B)
    val branch_jump_set_done_q=RegInit(false.B)
    val branch_set_raw_q=RegInit(false.B).suggestName("g_branch_set_flop_branch_set_raw_q")
    val instr_first_cycle=instr_valid_i && !id_fsm_q
    val instr_executing=instr_valid_i && !instr_fetch_err_i && ctrl.controller_run_o
    val phaseNeedsExecute=if(RegisteredExecution) !illegal_insn_o && !instr_fetch_err_i &&
      !ecallInstruction && !ebreakInstruction && !(id_fsm_q && dataRequest) else false.B
    if(RegisteredExecution) {
      executionPhaseReady:=decodeReady && (!phaseNeedsExecute || ex_valid_i)
      execute_req_o.get:=instr_executing && decodeReady && phaseNeedsExecute
      execute_consume_o.get:=instr_executing && phaseNeedsExecute && ex_valid_i && ready_wb_i
    }
    val id_fsm_d=WireDefault(id_fsm_q)
    val rf_we_raw=WireDefault(integerWrite)
    val stall_multdiv=WireDefault(false.B); val stall_jump=WireDefault(false.B)
    val stall_branch=WireDefault(false.B); val stall_alu=WireDefault(false.B)
    val branch_set_raw_d=WireDefault(false.B); val jump_set_raw=WireDefault(false.B)
    val multdiv_en_dec=multiplyEnable || divideEnable ||
      (if(WithF && !RegisteredExecution) fp_arithmetic_i.get else false.B)
    val multicycle_done=Mux(dataRequest,lsu_resp_valid_i,ex_valid_i)
    perf_branch_o:=false.B
    when(instr_executing && executionPhaseReady) {
      when(!id_fsm_q) {
        when(dataRequest) { id_fsm_d:=true.B }
          .elsewhen(multdiv_en_dec) {
            when(!ex_valid_i) { id_fsm_d:=true.B; rf_we_raw:=false.B; stall_multdiv:=true.B }
          }.elsewhen(branchInstruction) {
            id_fsm_d:=data_ind_timing_i || branch_decision_i
            stall_branch:=branch_decision_i || data_ind_timing_i
            branch_set_raw_d:=branch_decision_i || data_ind_timing_i; perf_branch_o:=true.B
          }.elsewhen(jumpInstruction) {
            id_fsm_d:=true.B; stall_jump:=true.B; jump_set_raw:=jumpSet
          }.elsewhen(dec.alu_multicycle_o) {
            id_fsm_d:=true.B; stall_alu:=true.B; rf_we_raw:=false.B
          }.otherwise { id_fsm_d:=false.B }
      }.otherwise {
        when(multdiv_en_dec) { rf_we_raw:=integerWrite && ex_valid_i }
        when(multicycle_done && ready_wb_i) { id_fsm_d:=false.B }
          .otherwise { stall_multdiv:=multdiv_en_dec; stall_branch:=branchInstruction; stall_jump:=jumpInstruction }
      }
      id_fsm_q:=id_fsm_d
    }
    if(RegisteredExecution || WithF) {
      // A controller flush cancels the old instruction's phase as well as its
      // qualification state; the next instruction must start with an address/
      // execution request even if the previous LSU operation ended in error.
      when(instr_valid_clear_o) { id_fsm_q:=false.B }
    }
    if(RegisteredExecution) {
      when(executionPhaseReady || instr_valid_clear_o) { branch_set_raw_q:=branch_set_raw_d }
    } else { branch_set_raw_q:=branch_set_raw_d }
    branch_jump_set_done_q:=((branch_set_raw_q && executionPhaseReady) || jump_set_raw || branch_jump_set_done_q) && !instr_valid_clear_o
    ctrl.jump_set_i:=jump_set_raw && !branch_jump_set_done_q
    ctrl.branch_set_i:=branch_set_raw_q && !branch_jump_set_done_q && executionPhaseReady
    val stall_mem=instr_valid_i && dataRequest && (!lsu_resp_valid_i || instr_first_cycle)
    // Resolve operation/phase stalls before applying the controller-run
    // qualifier. The individual strobes above remain for their original
    // writeback/performance semantics, but need not form a priority path from
    // controller state through ID and back to fetch acceptance.
    val firstPhaseStall=Mux(dataRequest,false.B,Mux(multdiv_en_dec,!ex_valid_i,
      Mux(branchInstruction,branch_decision_i || data_ind_timing_i,
        jumpInstruction || dec.alu_multicycle_o)))
    val nextPhaseStall= !(multicycle_done && ready_wb_i) &&
      (multdiv_en_dec || branchInstruction || jumpInstruction)
    val phaseStall=Mux(id_fsm_q,nextPhaseStall,firstPhaseStall)
    val stall_id=stall_mem || (instr_executing && (!executionPhaseReady || phaseStall))
    ctrl.stall_id_i:=stall_id
    val instr_done= !stall_id && !ctrl.flush_id_o && instr_executing
    if(WithF && !RegisteredExecution) {
      execute_req_o.get:=instr_executing && decodeReady && fp_arithmetic_i.get && !illegal_insn_o
      execute_consume_o.get:=instr_done && fp_arithmetic_i.get
    }
    dec.instr_first_cycle_i:=instr_first_cycle; instr_first_cycle_id_o:=instr_first_cycle
    instr_id_done_o:=instr_done; en_wb_o:=instr_done
    if(WithF) {
      // A load's response phase has no branch/execute stall. Resolve its
      // architectural commit directly instead of routing through that tree.
      fp_load_commit_o.get:=instr_executing && !ctrl.flush_id_o && dataRequest &&
        !instr_first_cycle && !storeInstruction && lsu_resp_valid_i
    }
    lsu_req_o:=instr_executing && instr_first_cycle && dataRequest && executionPhaseReady
    mult_en_ex_o:=instr_executing && multiplyEnable; div_en_ex_o:=instr_executing && divideEnable
    if(RegisteredExecution) {
      // A qualified CSR instruction is a single ALU phase, never an LSU,
      // branch, jump or M instruction. Commit on its accepted response rather
      // than the general instruction-done tree that also includes LSU stalls.
      csr_op_en_o:=csrInstruction && execute_consume_o.get && decodeReady && !illegal_insn_o
    } else { csr_op_en_o:=csrInstruction && instr_executing && instr_done }
    rf_we_id_o:=rf_we_raw && instr_executing && !effectiveIllegalCsr && executionPhaseReady && fpEffectsAllowed
    expecting_load_resp_o:=instr_valid_i && dataRequest && !instr_first_cycle && !storeInstruction
    expecting_store_resp_o:=instr_valid_i && dataRequest && !instr_first_cycle && storeInstruction
    perf_dside_wait_o:=instr_executing && dataRequest && !lsu_resp_valid_i
    perf_mul_wait_o:=stall_multdiv && multiplyEnable; perf_div_wait_o:=stall_multdiv && divideEnable
  }
  instr_perf_count_id_o:= !dec.ebrk_insn_o && !dec.ecall_insn_o && !dec.illegal_insn_o &&
    !effectiveIllegalCsr && !instr_fetch_err_i && fpEffectsAllowed
}
