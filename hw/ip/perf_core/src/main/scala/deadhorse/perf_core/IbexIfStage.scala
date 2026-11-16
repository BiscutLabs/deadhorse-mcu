// Copyright lowRISC contributors.
// Copyright 2018 ETH Zurich and University of Bologna; see upstream CREDITS.md.
// Licensed under Apache-2.0; SPDX-License-Identifier: Apache-2.0
// Translation of rtl/ibex_if_stage.sv, Ibex
// 38c070939183cc10940b66c8e9e04eeca6b65470, pinned non-secure/no-cache profile.
package deadhorse.perf_core

import chisel3._
import chisel3.util.{Cat, Mux1H}

class IbexIfStage(val DmHaltAddr: BigInt = BigInt("1a110800",16),
    val DmExceptionAddr: BigInt = BigInt("1a110808",16),
    val DummyInstructions: Boolean = false, val ICache: Boolean = false,
    val ICacheECC: Boolean = false, val BusSizeECC: Int = 32,
    val TagSizeECC: Int = 22, val LineSizeECC: Int = 64,
    val PCIncrCheck: Boolean = false, val ResetAll: Boolean = false,
    val RndCnstLfsrSeed: BigInt = BigInt("ac533bf4",16),
    val RndCnstLfsrPerm: BigInt = BigInt("1e35ecba467fd1b12e958152c04fa43878a8daed",16),
    val BranchPredictor: Boolean = false, val MemECC: Boolean = false,
    val MemDataWidth: Int = 32, val RegisteredRedirect: Boolean = false) extends RawModule {
  require(!DummyInstructions && !ICache && !ICacheECC && !PCIncrCheck && !ResetAll && !BranchPredictor && !MemECC)
  require(BusSizeECC==32 && TagSizeECC==22 && LineSizeECC==64 && MemDataWidth==32)
  require(DmHaltAddr>=0 && DmHaltAddr<(BigInt(1)<<32) && DmExceptionAddr>=0 && DmExceptionAddr<(BigInt(1)<<32))
  override def desiredName = "ibex_if_stage"
  val clk_i = IO(Input(Clock())); val rst_ni = IO(Input(Bool()))
  val boot_addr_i = IO(Input(UInt(32.W))); val req_i = IO(Input(Bool()))
  val instr_req_o = IO(Output(Bool())); val instr_addr_o = IO(Output(UInt(32.W)))
  val instr_gnt_i = IO(Input(Bool())); val instr_rvalid_i = IO(Input(Bool()))
  val instr_rdata_i = IO(Input(UInt(32.W))); val instr_bus_err_i = IO(Input(Bool()))
  val instr_intg_err_o = IO(Output(Bool()))
  val ic_tag_req_o = IO(Output(UInt(2.W))); val ic_tag_write_o = IO(Output(Bool()))
  val ic_tag_addr_o = IO(Output(UInt(8.W))); val ic_tag_wdata_o = IO(Output(UInt(22.W)))
  val ic_tag_rdata_i = IO(Input(UInt(44.W)))
  val ic_data_req_o = IO(Output(UInt(2.W))); val ic_data_write_o = IO(Output(Bool()))
  val ic_data_addr_o = IO(Output(UInt(8.W))); val ic_data_wdata_o = IO(Output(UInt(64.W)))
  val ic_data_rdata_i = IO(Input(UInt(128.W)))
  val ic_scr_key_valid_i = IO(Input(Bool())); val ic_scr_key_req_o = IO(Output(Bool()))
  val instr_valid_id_o = IO(Output(Bool())); val instr_new_id_o = IO(Output(Bool()))
  val instr_rdata_id_o = IO(Output(UInt(32.W))); val instr_rdata_alu_id_o = IO(Output(UInt(32.W)))
  val instr_rdata_c_id_o = IO(Output(UInt(16.W))); val instr_is_compressed_id_o = IO(Output(Bool()))
  val instr_bp_taken_o = IO(Output(Bool())); val instr_fetch_err_o = IO(Output(Bool()))
  val instr_fetch_err_plus2_o = IO(Output(Bool())); val illegal_c_insn_id_o = IO(Output(Bool()))
  val dummy_instr_id_o = IO(Output(Bool())); val pc_if_o = IO(Output(UInt(32.W)))
  val pc_id_o = IO(Output(UInt(32.W)))
  val pmp_err_if_i = IO(Input(Bool())); val pmp_err_if_plus2_i = IO(Input(Bool()))
  val instr_valid_clear_i = IO(Input(Bool())); val pc_set_i = IO(Input(Bool()))
  val pc_mux_i = IO(Input(UInt(3.W))); val nt_branch_mispredict_i = IO(Input(Bool()))
  val nt_branch_addr_i = IO(Input(UInt(32.W))); val exc_pc_mux_i = IO(Input(UInt(2.W)))
  val exc_cause = IO(Input(UInt(7.W))) // packed irq_int, irq_ext, lower_cause
  val dummy_instr_en_i = IO(Input(Bool())); val dummy_instr_mask_i = IO(Input(UInt(3.W)))
  val dummy_instr_seed_en_i = IO(Input(Bool())); val dummy_instr_seed_i = IO(Input(UInt(32.W)))
  val icache_enable_i = IO(Input(Bool())); val icache_inval_i = IO(Input(Bool()))
  val icache_ecc_error_o = IO(Output(Bool()))
  val branch_target_ex_i = IO(Input(UInt(32.W)))
  val csr_mepc_i = IO(Input(UInt(32.W))); val csr_depc_i = IO(Input(UInt(32.W)))
  val csr_mtvec_i = IO(Input(UInt(32.W))); val csr_mtvec_init_o = IO(Output(Bool()))
  val id_in_ready_i = IO(Input(Bool())); val pc_mismatch_alert_o = IO(Output(Bool()))
  val if_busy_o = IO(Output(Bool()))

  val irq_vec = Mux(exc_cause(6),31.U(5.W),exc_cause(4,0))
  // Decode the mutually exclusive PC choices in parallel. The boot default
  // also covers reserved 3-bit encodings, preserving the reference there.
  val exc_pc = Mux1H(Seq(
    (exc_pc_mux_i===0.U) -> Cat(csr_mtvec_i(31,8),0.U(8.W)),
    (exc_pc_mux_i===1.U) -> Cat(csr_mtvec_i(31,8),false.B,irq_vec,0.U(2.W)),
    (exc_pc_mux_i===2.U) -> DmHaltAddr.U(32.W),
    (exc_pc_mux_i===3.U) -> DmExceptionAddr.U(32.W)))
  val fetch_addr_n = Mux1H(Seq(
    (pc_mux_i===0.U || pc_mux_i>=5.U) -> Cat(boot_addr_i(31,8),0x80.U(8.W)),
    (pc_mux_i===1.U) -> branch_target_ex_i,(pc_mux_i===2.U) -> exc_pc,
    (pc_mux_i===3.U) -> csr_mepc_i,(pc_mux_i===4.U) -> csr_depc_i))
  csr_mtvec_init_o := pc_mux_i === 0.U && pc_set_i
  val gen_prefetch_buffer_prefetch_buffer_i = Module(new IbexPrefetchBuffer)
  val prefetch = gen_prefetch_buffer_prefetch_buffer_i
  val rawRedirect=pc_set_i || nt_branch_mispredict_i
  val rawRedirectAddr=Mux(pc_set_i,Cat(fetch_addr_n(31,1),false.B),nt_branch_addr_i)
  val redirect=WireDefault(rawRedirect)
  val redirectAddr=WireDefault(rawRedirectAddr)
  val redirectBlocksFetch=WireDefault(false.B)
  if(RegisteredRedirect) {
    withClockAndReset(clk_i,(!rst_ni).asAsyncReset) {
      val redirect_pending_q=RegNext(rawRedirect,false.B)
      val redirect_addr_q=Reg(UInt(32.W))
      when(rawRedirect) { redirect_addr_q:=rawRedirectAddr }
      redirect:=redirect_pending_q; redirectAddr:=redirect_addr_q
      redirectBlocksFetch:=rawRedirect || redirect_pending_q
    }
  }
  prefetch.clk_i := clk_i; prefetch.rst_ni := rst_ni
  prefetch.req_i := req_i && (if(RegisteredRedirect) !rawRedirect else true.B)
  prefetch.branch_i := redirect
  prefetch.addr_i := redirectAddr
  prefetch.ready_i := id_in_ready_i && !redirectBlocksFetch
  prefetch.instr_gnt_i := instr_gnt_i; prefetch.instr_rvalid_i := instr_rvalid_i
  prefetch.instr_rdata_i := instr_rdata_i; prefetch.instr_err_i := instr_bus_err_i
  instr_req_o := prefetch.instr_req_o; instr_addr_o := prefetch.instr_addr_o
  if_busy_o := prefetch.busy_o; pc_if_o := prefetch.addr_o
  // Hold the current ID instruction until its original controller clear.
  // In particular, JAL/JALR redirect before their second (link) phase finishes.
  // Only new FIFO-to-ID transfers are suppressed across the redirect register.
  val fetch_valid = prefetch.valid_o && !nt_branch_mispredict_i && !redirectBlocksFetch
  val compressed_decoder_i = Module(new IbexCompressedDecoder)
  compressed_decoder_i.clk_i := clk_i; compressed_decoder_i.rst_ni := rst_ni
  compressed_decoder_i.valid_i := fetch_valid && !prefetch.err_o
  compressed_decoder_i.instr_i := prefetch.rdata_o
  val pmpPlus2 = prefetch.addr_o(1) && !compressed_decoder_i.is_compressed_o && pmp_err_if_plus2_i
  val instrError = prefetch.err_o || pmp_err_if_i || pmpPlus2
  val instrErrorPlus2 = (pmpPlus2 || prefetch.err_plus2_o) && !pmp_err_if_i
  val newInstruction = fetch_valid && id_in_ready_i
  val instr_valid_id_d = Wire(Bool())
  val instr_new_id_d = newInstruction
  withClockAndReset(clk_i,(!rst_ni).asAsyncReset) {
    val instr_valid_id_q = RegInit(false.B)
    val instr_new_id_q = RegInit(false.B)
    instr_valid_id_d := (newInstruction && !pc_set_i) || (instr_valid_id_q && !instr_valid_clear_i)
    instr_valid_id_q := instr_valid_id_d
    instr_new_id_q := newInstruction
    instr_valid_id_o := instr_valid_id_q; instr_new_id_o := instr_new_id_q
    // These flops intentionally have no reset in the pinned configuration.
    val instr_rdata_id_q = Reg(UInt(32.W)); val instr_rdata_alu_id_q = Reg(UInt(32.W))
    val instr_rdata_c_id_q = Reg(UInt(16.W)); val instr_compressed_q = Reg(Bool())
    val instr_fetch_err_q = Reg(Bool()); val instr_fetch_err_plus2_q = Reg(Bool())
    val illegal_c_insn_q = Reg(Bool()); val pc_id_q = Reg(UInt(32.W))
    when(newInstruction) {
      instr_rdata_id_q := compressed_decoder_i.instr_o; instr_rdata_alu_id_q := compressed_decoder_i.instr_o
      instr_rdata_c_id_q := prefetch.rdata_o(15,0); instr_compressed_q := compressed_decoder_i.is_compressed_o
      instr_fetch_err_q := instrError; instr_fetch_err_plus2_q := instrErrorPlus2
      illegal_c_insn_q := compressed_decoder_i.illegal_instr_o; pc_id_q := prefetch.addr_o
    }
    instr_rdata_id_o := instr_rdata_id_q; instr_rdata_alu_id_o := instr_rdata_alu_id_q
    instr_rdata_c_id_o := instr_rdata_c_id_q; instr_is_compressed_id_o := instr_compressed_q
    instr_fetch_err_o := instr_fetch_err_q; instr_fetch_err_plus2_o := instr_fetch_err_plus2_q
    illegal_c_insn_id_o := illegal_c_insn_q; pc_id_o := pc_id_q
  }
  instr_intg_err_o := false.B; instr_bp_taken_o := false.B; dummy_instr_id_o := false.B
  pc_mismatch_alert_o := false.B; icache_ecc_error_o := false.B
  ic_tag_req_o := 0.U; ic_tag_write_o := false.B; ic_tag_addr_o := 0.U; ic_tag_wdata_o := 0.U
  ic_data_req_o := 0.U; ic_data_write_o := false.B; ic_data_addr_o := 0.U; ic_data_wdata_o := 0.U
  ic_scr_key_req_o := false.B
}
