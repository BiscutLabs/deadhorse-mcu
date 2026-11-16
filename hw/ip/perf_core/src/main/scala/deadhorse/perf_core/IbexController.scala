// Copyright lowRISC contributors.
// Copyright 2018 ETH Zurich and University of Bologna; see upstream CREDITS.md.
// Licensed under Apache-2.0; SPDX-License-Identifier: Apache-2.0
// Translation of rtl/ibex_controller.sv, Ibex
// 38c070939183cc10940b66c8e9e04eeca6b65470, pinned two-stage/non-ECC profile.
package deadhorse.perf_core

import chisel3._
import chisel3.util.{Cat, addAttribute, is, switch}

class IbexController(val WritebackStage: Boolean = false,
    val BranchPredictor: Boolean = false, val MemECC: Boolean = false,
    val RegisteredExecution: Boolean = false) extends RawModule {
  require(!WritebackStage && !BranchPredictor && !MemECC,"T11 implements the pinned controller")
  override def desiredName = "ibex_controller"
  val clk_i = IO(Input(Clock())); val rst_ni = IO(Input(Bool()))
  val ctrl_busy_o = IO(Output(Bool()))
  val illegal_insn_i = IO(Input(Bool())); val ecall_insn_i = IO(Input(Bool()))
  val mret_insn_i = IO(Input(Bool())); val dret_insn_i = IO(Input(Bool()))
  val wfi_insn_i = IO(Input(Bool())); val ebrk_insn_i = IO(Input(Bool()))
  val csr_pipe_flush_i = IO(Input(Bool())); val instr_valid_i = IO(Input(Bool()))
  val instr_i = IO(Input(UInt(32.W))); val instr_compressed_i = IO(Input(UInt(16.W)))
  val instr_is_compressed_i = IO(Input(Bool())); val instr_bp_taken_i = IO(Input(Bool()))
  val instr_fetch_err_i = IO(Input(Bool())); val instr_fetch_err_plus2_i = IO(Input(Bool()))
  val pc_id_i = IO(Input(UInt(32.W)))
  val instr_valid_clear_o = IO(Output(Bool())); val id_in_ready_o = IO(Output(Bool()))
  val controller_run_o = IO(Output(Bool())); val instr_exec_i = IO(Input(Bool()))
  val instr_req_o = IO(Output(Bool())); val pc_set_o = IO(Output(Bool()))
  val pc_mux_o = IO(Output(UInt(3.W))); val nt_branch_mispredict_o = IO(Output(Bool()))
  val exc_pc_mux_o = IO(Output(UInt(2.W))); val exc_cause_o = IO(Output(UInt(7.W)))
  val lsu_addr_last_i = IO(Input(UInt(32.W))); val load_err_i = IO(Input(Bool()))
  val store_err_i = IO(Input(Bool())); val mem_resp_intg_err_i = IO(Input(Bool()))
  val wb_exception_o = IO(Output(Bool())); val id_exception_o = IO(Output(Bool()))
  val branch_set_i = IO(Input(Bool())); val branch_not_set_i = IO(Input(Bool())); val jump_set_i = IO(Input(Bool()))
  val csr_mstatus_mie_i = IO(Input(Bool())); val irq_pending_i = IO(Input(Bool()))
  val irqs_i = IO(Input(UInt(18.W))) // software, timer, external, fast[14:0]
  val irq_nm_ext_i = IO(Input(Bool())); val nmi_mode_o = IO(Output(Bool()))
  val debug_req_i = IO(Input(Bool())); val debug_cause_o = IO(Output(UInt(3.W)))
  val debug_csr_save_o = IO(Output(Bool())); val debug_mode_o = IO(Output(Bool()))
  val debug_mode_entering_o = IO(Output(Bool()))
  val debug_single_step_i = IO(Input(Bool())); val debug_ebreakm_i = IO(Input(Bool()))
  val debug_ebreaku_i = IO(Input(Bool())); val trigger_match_i = IO(Input(Bool()))
  val csr_save_if_o = IO(Output(Bool())); val csr_save_id_o = IO(Output(Bool()))
  val csr_save_wb_o = IO(Output(Bool())); val csr_restore_mret_id_o = IO(Output(Bool()))
  val csr_restore_dret_id_o = IO(Output(Bool())); val csr_save_cause_o = IO(Output(Bool()))
  val csr_mtval_o = IO(Output(UInt(32.W))); val priv_mode_i = IO(Input(UInt(2.W)))
  val stall_id_i = IO(Input(Bool())); val stall_wb_i = IO(Input(Bool()))
  val flush_id_o = IO(Output(Bool())); val ready_wb_i = IO(Input(Bool()))
  val perf_jump_o = IO(Output(Bool())); val perf_tbranch_o = IO(Output(Bool()))
  val execute_phase_ready_i=if(RegisteredExecution) Some(IO(Input(Bool()))) else None
  // Internal observation point used by the parent RVFI monitor, as upstream.
  val rvfi_flush_next = Wire(Bool())
  val phase_decode_consistent=WireDefault(true.B)

  private val resetState=0.U(4.W); private val bootSet=1.U(4.W)
  private val waitSleep=2.U(4.W); private val sleepState=3.U(4.W)
  private val firstFetch=4.U(4.W); private val decode=5.U(4.W)
  private val flush=6.U(4.W); private val irqTaken=7.U(4.W)
  private val debugTakenIf=8.U(4.W); private val debugTakenId=9.U(4.W)
  withClockAndReset(clk_i,(!rst_ni).asAsyncReset) {
    val ctrl_fsm_cs=RegInit(resetState)
    val nmi_mode_q=RegInit(false.B); val debug_mode_q=RegInit(false.B)
    val debug_cause_q=RegInit(0.U(3.W))
    val load_err_q=RegInit(false.B); val store_err_q=RegInit(false.B)
    val exc_req_q=RegInit(false.B); val illegal_insn_q=RegInit(false.B)
    val do_single_step_q=RegInit(false.B); val enter_debug_mode_prio_q=RegInit(false.B)
    val ctrl_fsm_ns=WireDefault(ctrl_fsm_cs)
    // Cached predicates in the registered profile preserve the same FSM
    // cycle/state while removing its binary decode from the ID/fetch roundtrip.
    def phaseDecode(predicate: UInt=>Bool):Bool = if(RegisteredExecution) {
      // All three cached predicates are false in resetState (encoding zero).
      val decoded=RegInit(false.B)
      decoded:=predicate(ctrl_fsm_ns)
      decoded
    } else predicate(ctrl_fsm_cs)
    val decodeState=phaseDecode(_===decode)
    val eventState=phaseDecode(s=>s===firstFetch || s===decode)
    val quietState=phaseDecode(s=>s===waitSleep || s===sleepState || s===flush)
    phase_decode_consistent:=decodeState===(ctrl_fsm_cs===decode) &&
      eventState===(ctrl_fsm_cs===firstFetch || ctrl_fsm_cs===decode) &&
      quietState===(ctrl_fsm_cs===waitSleep || ctrl_fsm_cs===sleepState || ctrl_fsm_cs===flush)
    rvfi_flush_next := ctrl_fsm_ns === flush
    val nmi_mode_d=WireDefault(nmi_mode_q); val debug_mode_d=WireDefault(debug_mode_q)
    val halt_if=WireDefault(false.B); val retain_id=WireDefault(false.B); val flush_id=WireDefault(false.B)
    val ecall=ecall_insn_i && instr_valid_i
    val mret=mret_insn_i && instr_valid_i; val dret=dret_insn_i && instr_valid_i
    val wfi=wfi_insn_i && instr_valid_i; val ebreak=ebrk_insn_i && instr_valid_i
    val csrFlush=csr_pipe_flush_i && instr_valid_i
    val fetchError=instr_fetch_err_i && instr_valid_i
    val illegal_insn_d=illegal_insn_i && ctrl_fsm_cs =/= flush
    val exc_req_d=(ecall || ebreak || illegal_insn_d || fetchError) && ctrl_fsm_cs =/= flush
    val special= mret || dret || exc_req_d || store_err_i || load_err_i || wfi || csrFlush
    val pending=instr_valid_i || !ready_wb_i
    val stall=stall_id_i || stall_wb_i
    val ebreakPriority=ebreak && !fetchError && !illegal_insn_q && !ecall
    val ebreakDebug=Mux(priv_mode_i === 3.U,debug_ebreakm_i,Mux(priv_mode_i === 0.U,debug_ebreaku_i,false.B))
    val do_single_step_d=Mux(instr_valid_i,!debug_mode_q && debug_single_step_i,do_single_step_q)
    val enter_debug_mode_prio_d=(debug_req_i || do_single_step_d) && !debug_mode_q
    val enterDebug=enter_debug_mode_prio_d || (trigger_match_i && !debug_mode_q)
    val handleIrq= !debug_mode_q && !debug_single_step_i && !nmi_mode_q &&
      (irq_nm_ext_i || (irq_pending_i && (csr_mstatus_mie_i || priv_mode_i === 0.U)))
    // Lowest numbered pending fast IRQ wins, as in the reference priority loop.
    // Parallel prefix qualification avoids a serial mux chain through the ID.
    val fastSelected=(0 until 15).map { index=>
      val selected=WireDefault(irqs_i(index) && (if(index==0) true.B else !irqs_i(index-1,0).orR))
      addAttribute(selected,"keep = 1")
      selected
    }
    val fastId=Cat((0 until 4).reverse.map { bit=>
      (0 until 15).filter(index=>(index & (1<<bit))!=0).map(fastSelected(_)).reduce(_||_)
    })
    val faultPcChunks=(1 until 32 by 4).map { low=>
      val high=math.min(low+3,31)
      val word=pc_id_i(high,low)
      val incremented=WireDefault(word+1.U((high-low+1).W))
      val carry=WireDefault(if(low==1) true.B else pc_id_i(low-1,1).andR)
      addAttribute(incremented,"keep = 1"); addAttribute(carry,"keep = 1")
      Mux(carry,incremented,word)
    }
    val faultPcPlus2=Cat(Cat(faultPcChunks.reverse),pc_id_i(0))
    debug_cause_q := Mux(trigger_match_i,2.U,Mux(ebreakPriority && ebreakDebug,1.U,
      Mux(debug_req_i,3.U,Mux(do_single_step_d,4.U,0.U))))
    load_err_q := load_err_i; store_err_q := store_err_i
    illegal_insn_q := illegal_insn_d; exc_req_q := exc_req_d
    do_single_step_q := do_single_step_d; enter_debug_mode_prio_q := enter_debug_mode_prio_d
    wb_exception_o := false.B; id_exception_o := exc_req_d
    debug_cause_o := debug_cause_q; debug_mode_o := debug_mode_q; nmi_mode_o := nmi_mode_q
    instr_req_o := true.B; ctrl_busy_o := true.B; controller_run_o := decodeState
    csr_save_if_o := false.B; csr_save_id_o := false.B; csr_save_wb_o := false.B
    csr_restore_mret_id_o := false.B; csr_restore_dret_id_o := false.B
    csr_save_cause_o := false.B; csr_mtval_o := 0.U
    pc_mux_o := 0.U; pc_set_o := false.B; nt_branch_mispredict_o := false.B
    exc_pc_mux_o := 1.U; exc_cause_o := 0.U
    debug_csr_save_o := false.B; debug_mode_entering_o := false.B
    perf_jump_o := false.B; perf_tbranch_o := false.B
    switch(ctrl_fsm_cs) {
      is(resetState) { instr_req_o := false.B; pc_set_o := true.B; ctrl_fsm_ns := bootSet }
      is(bootSet) { pc_set_o := true.B; ctrl_fsm_ns := firstFetch }
      is(waitSleep) {
        ctrl_busy_o := false.B; instr_req_o := false.B; halt_if := true.B; flush_id := true.B
        ctrl_fsm_ns := sleepState
      }
      is(sleepState) {
        instr_req_o := false.B; halt_if := true.B; flush_id := true.B
        when(irq_nm_ext_i || irq_pending_i || debug_req_i || debug_mode_q || debug_single_step_i) {
          ctrl_fsm_ns := firstFetch
        }.otherwise { ctrl_busy_o := false.B }
      }
      is(firstFetch) {
        when(id_in_ready_o) { ctrl_fsm_ns := decode }
        when(handleIrq) { ctrl_fsm_ns := irqTaken; halt_if := true.B }
        when(enterDebug) { ctrl_fsm_ns := debugTakenIf; halt_if := true.B }
      }
      is(decode) {
        pc_mux_o := 1.U
        when(special) {
          retain_id := true.B
          when(ready_wb_i && execute_phase_ready_i.getOrElse(true.B)) { ctrl_fsm_ns := flush }
        }
        when(branch_set_i || jump_set_i) {
          pc_set_o := true.B; perf_tbranch_o := branch_set_i; perf_jump_o := jump_set_i
        }
        when((enterDebug || handleIrq) && (stall || pending)) { halt_if := true.B }
        when(!stall && !special && !pending) {
          when(enterDebug) { ctrl_fsm_ns := debugTakenIf; halt_if := true.B }
            .elsewhen(handleIrq) { ctrl_fsm_ns := irqTaken; halt_if := true.B }
        }
      }
      is(irqTaken) {
        pc_mux_o := 2.U; exc_pc_mux_o := 1.U; ctrl_fsm_ns := decode
        when(handleIrq) {
          pc_set_o := true.B; csr_save_if_o := true.B; csr_save_cause_o := true.B
          when(irq_nm_ext_i && !nmi_mode_q) { exc_cause_o := 63.U; nmi_mode_d := true.B }
            .elsewhen(irqs_i(14,0).orR) { exc_cause_o := Cat(0.U(1.W),3.U(2.W),fastId) }
            .elsewhen(irqs_i(15)) { exc_cause_o := 43.U }
            .elsewhen(irqs_i(17)) { exc_cause_o := 35.U }
            .otherwise { exc_cause_o := 39.U }
        }
      }
      is(debugTakenIf) {
        pc_mux_o := 2.U; exc_pc_mux_o := 2.U; flush_id := true.B; pc_set_o := true.B
        csr_save_if_o := true.B; debug_csr_save_o := true.B; csr_save_cause_o := true.B
        debug_mode_d := true.B; debug_mode_entering_o := true.B; ctrl_fsm_ns := decode
      }
      is(debugTakenId) {
        flush_id := true.B; pc_mux_o := 2.U; pc_set_o := true.B; exc_pc_mux_o := 2.U
        when(ebreakDebug && !debug_mode_q) {
          csr_save_cause_o := true.B; csr_save_id_o := true.B; debug_csr_save_o := true.B
        }
        debug_mode_d := true.B; debug_mode_entering_o := true.B; ctrl_fsm_ns := decode
      }
      is(flush) {
        halt_if := true.B; flush_id := true.B; ctrl_fsm_ns := decode
        when(exc_req_q || store_err_q || load_err_q) {
          pc_set_o := true.B; pc_mux_o := 2.U; exc_pc_mux_o := Mux(debug_mode_q,3.U,0.U)
          // Faithful pinned no-writeback behavior, including zero save_id.
          csr_save_cause_o := true.B
          when(fetchError) {
            exc_cause_o := 1.U; csr_mtval_o := Mux(instr_fetch_err_plus2_i,faultPcPlus2,pc_id_i)
          }.elsewhen(illegal_insn_q) {
            exc_cause_o := 2.U; csr_mtval_o := Mux(instr_is_compressed_i,instr_compressed_i.pad(32),instr_i)
          }.elsewhen(ecall) { exc_cause_o := Mux(priv_mode_i === 3.U,11.U,8.U) }
            .elsewhen(ebreak) {
              when(debug_mode_q || ebreakDebug) {
                pc_set_o := false.B; csr_save_cause_o := false.B; ctrl_fsm_ns := debugTakenId; flush_id := false.B
              }.otherwise { exc_cause_o := 3.U }
            }.elsewhen(store_err_q) { exc_cause_o := 7.U; csr_mtval_o := lsu_addr_last_i }
            .elsewhen(load_err_q) { exc_cause_o := 5.U; csr_mtval_o := lsu_addr_last_i }
        }.otherwise {
          when(mret) {
            pc_mux_o := 3.U; pc_set_o := true.B; csr_restore_mret_id_o := true.B
            when(nmi_mode_q) { nmi_mode_d := false.B }
          }.elsewhen(dret) {
            pc_mux_o := 4.U; pc_set_o := true.B; debug_mode_d := false.B; csr_restore_dret_id_o := true.B
          }.elsewhen(wfi) { ctrl_fsm_ns := waitSleep }
        }
        when(enter_debug_mode_prio_q && !(ebreakPriority && ebreakDebug)) { ctrl_fsm_ns := debugTakenIf }
      }
    }
    when(ctrl_fsm_cs > debugTakenId) { instr_req_o := false.B; ctrl_fsm_ns := resetState }
    when(!instr_exec_i) { halt_if := true.B }
    ctrl_fsm_cs := ctrl_fsm_ns; nmi_mode_q := nmi_mode_d; debug_mode_q := debug_mode_d
    flush_id_o := flush_id
    // Factor the acceptance predicate directly. In DECODE, a special
    // instruction retains ID; otherwise any pending IRQ/debug entry halts IF,
    // regardless of whether the current instruction is still pending. This
    // avoids routing fetch readiness through the priority output mux tree.
    val eventBlocksFetch=eventState && (enterDebug || handleIrq)
    id_in_ready_o := instr_exec_i && !stall && !quietState && !eventBlocksFetch &&
      !(decodeState && special)
    instr_valid_clear_o := !(stall || retain_id) || flush_id
  }
}
