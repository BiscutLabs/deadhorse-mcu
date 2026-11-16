// Copyright 2026 Deadhorse contributors. Apache-2.0.
package deadhorse.perf_core

import chisel3._
import chisel3.util._
import chisel3.util.experimental.BoringUtils
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files,Paths}

/** Integration safety, with arbitrary memory responses, IRQ/debug and resets.
  * Arithmetic and execution deadlines have their own checked contracts.
  */
class CoreIntegrationFormal(coversOnly:Boolean=false)
    extends IbexCore(WithRVFI=false,RegisteredExecution=true) {
  override def desiredName="CoreIntegrationFormal"
  val checking=IO(Input(Bool()))
  val unit=ex_block_i.clocked_execute.get
  val accepted=BoringUtils.bore(unit.req.valid) && BoringUtils.bore(unit.req.ready)
  val responseValid=BoringUtils.bore(unit.rsp.valid)
  val consumed=responseValid && BoringUtils.bore(unit.rsp.ready)
  val executionBusy=BoringUtils.bore(unit.busy_o)
  val request=BoringUtils.bore(unit.req.bits)
  val pending=withClockAndReset(clk_i,(!rst_ni).asAsyncReset) { RegInit(false.B) }
  val pc=withClockAndReset(clk_i,(!rst_ni).asAsyncReset) { RegInit(0.U(32.W)) }
  val instruction=withClockAndReset(clk_i,(!rst_ni).asAsyncReset) { RegInit(0.U(32.W)) }
  val firstPhase=withClockAndReset(clk_i,(!rst_ni).asAsyncReset) { RegInit(false.B) }
  val kind=withClockAndReset(clk_i,(!rst_ni).asAsyncReset) { RegInit(0.U(2.W)) }
  val nonzero=withClockAndReset(clk_i,(!rst_ni).asAsyncReset) { RegInit(false.B) }
  val issued=withClockAndReset(clk_i,(!rst_ni).asAsyncReset) { RegInit(0.U(2.W)) }
  val completed=withClockAndReset(clk_i,(!rst_ni).asAsyncReset) { RegInit(0.U(2.W)) }
  val phaseBit=Mux(id_stage_i.instr_first_cycle_id_o,1.U(2.W),2.U(2.W))
  val memoryInstruction=BoringUtils.bore(id_stage_i.decoder_i.data_req_o)
  val exceptionInstruction=id_stage_i.illegal_insn_o || if_stage_i.instr_fetch_err_o ||
    BoringUtils.bore(id_stage_i.decoder_i.ecall_insn_o) || BoringUtils.bore(id_stage_i.decoder_i.ebrk_insn_o)
  val redirectRequest=BoringUtils.bore(if_stage_i.rawRedirect)
  val redirectInput=BoringUtils.bore(if_stage_i.rawRedirectAddr)
  val redirectValid=BoringUtils.bore(if_stage_i.redirect)
  val redirectAddress=BoringUtils.bore(if_stage_i.redirectAddr)
  val fetchTransfer=BoringUtils.bore(if_stage_i.newInstruction)
  val fetchPop=BoringUtils.bore(if_stage_i.prefetch.ready_i)
  val controllerPhaseConsistent=BoringUtils.bore(id_stage_i.controller_i.phase_decode_consistent)
  val expectedRedirect=withClockAndReset(clk_i,(!rst_ni).asAsyncReset) { RegNext(redirectRequest,false.B) }
  val expectedAddress=withClockAndReset(clk_i,(!rst_ni).asAsyncReset) {
    RegEnable(redirectInput,0.U(32.W),redirectRequest)
  }
  withClockAndReset(clk_i,(!rst_ni).asAsyncReset) {
    when(accepted) {
      pending:=true.B; pc:=if_stage_i.pc_id_o; instruction:=if_stage_i.instr_rdata_id_o
      firstPhase:=id_stage_i.instr_first_cycle_id_o; kind:=request.kind; nonzero:=request.b=/=0.U
    }
    when(consumed) { pending:=false.B }
    when(accepted) { issued:=issued | phaseBit }
    when(consumed) { completed:=completed | phaseBit }
    when(id_stage_i.instr_valid_clear_o) { issued:=0.U; completed:=0.U }
  }
  withClockAndReset(clk_i,false.B) {
    val priorPending=RegNext(pending)
    if(coversOnly) cover(checking && !rst_ni && priorPending)
    when(checking && rst_ni) {
      if(coversOnly) {
        for(k<-0 until 4) cover(consumed && kind===k.U)
        cover(consumed && kind===2.U && nonzero)
        cover(id_stage_i.lsu_req_o)
        cover(id_stage_i.csr_op_en_o)
        cover(id_stage_i.pc_set_o && id_stage_i.pc_mux_o===1.U)
        cover(id_stage_i.debug_csr_save_o)
        cover(id_stage_i.csr_save_if_o && id_stage_i.csr_save_cause_o && !id_stage_i.debug_csr_save_o)
        cover(id_stage_i.csr_save_cause_o && exceptionInstruction && !id_stage_i.debug_csr_save_o)
        cover(redirectRequest && redirectValid && redirectInput=/=redirectAddress)
        cover(redirectValid && if_stage_i.instr_valid_id_o)
      } else {
        assert(pending===executionBusy)
        assert(!accepted || !pending)
        assert(!consumed || pending)
        when(pending) {
          assert(if_stage_i.instr_valid_id_o)
          assert(if_stage_i.pc_id_o===pc)
          assert(if_stage_i.instr_rdata_id_o===instruction)
          assert(id_stage_i.instr_first_cycle_id_o===firstPhase)
        }
        assert(!id_stage_i.lsu_req_o || (consumed && firstPhase))
        assert(!id_stage_i.csr_op_en_o || consumed)
        assert(!rf_we_wb_o || consumed || load_store_unit_i.lsu_rdata_valid_o)
        assert(!id_stage_i.instr_id_done_o || !pending || consumed)
        assert(!(id_stage_i.pc_set_o && id_stage_i.pc_mux_o===1.U) || consumed)
        assert(!load_store_unit_i.addr_incr_req_o ||
          load_store_unit_i.adder_result_ex_i===(load_store_unit_i.addr_last_o+4.U))
        assert(!accepted || (issued & phaseBit)===0.U)
        assert(!consumed || (completed & phaseBit)===0.U)
        when(id_stage_i.instr_id_done_o && !exceptionInstruction) {
          assert(consumed || (memoryInstruction && completed(0) && load_store_unit_i.lsu_resp_valid_o))
        }
        assert(!(id_stage_i.csr_save_cause_o || id_stage_i.csr_restore_mret_id_o ||
          id_stage_i.csr_restore_dret_id_o || id_stage_i.debug_csr_save_o) || !pending)
        assert(redirectValid===expectedRedirect)
        assert(!redirectValid || redirectAddress===expectedAddress)
        assert(!(redirectRequest || redirectValid) || (!fetchTransfer && !fetchPop))
        assert(controllerPhaseConsistent)
      }
    }
  }
}

object EmitCoreIntegrationFormal {
  def main(args:Array[String]):Unit={
    require(args.length==2)
    val output=Paths.get(args(0)).toAbsolutePath.normalize
    require(output.startsWith(Paths.get("build").toAbsolutePath.normalize))
    Files.createDirectories(output)
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(
      new CoreIntegrationFormal(args(1)=="cover")),
      Array("--target-dir",output.toString),Array("--disable-all-randomization",
        "--verification-flavor=immediate","--lower-to-core","-strip-debug-info","--preserve-values=named"))
  }
}
