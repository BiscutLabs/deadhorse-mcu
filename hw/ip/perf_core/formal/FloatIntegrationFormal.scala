package deadhorse.perf_core

import chisel3._
import chisel3.util._
import chisel3.util.experimental.BoringUtils
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files,Paths}

/** Production control instrumentation; arithmetic remains a separate obligation. */
class FloatIntegrationFormal(coversOnly:Boolean=false)
    extends IbexCore(WithRVFI=false,RegisteredExecution=true,WithF=true) {
  override def desiredName="FloatIntegrationFormal"
  val checking=IO(Input(Bool()))
  val fp=floatExecution.get
  val accepted=(BoringUtils.bore(fp.fpu.io.req.valid) && BoringUtils.bore(fp.fpu.io.req.ready))
  val response=BoringUtils.bore(fp.fpu.io.rsp.valid)
  val consumed=(BoringUtils.bore(fp.fpu.io.rsp.valid) && BoringUtils.bore(fp.fpu.io.rsp.ready))
  val cancel=fp.io.cancel
  val intAccepted=(BoringUtils.bore(ex_block_i.clocked_execute.get.req.valid) && BoringUtils.bore(ex_block_i.clocked_execute.get.req.ready))
  val intConsumed=(BoringUtils.bore(ex_block_i.clocked_execute.get.rsp.valid) && BoringUtils.bore(ex_block_i.clocked_execute.get.rsp.ready))
  val intResponse=BoringUtils.bore(ex_block_i.clocked_execute.get.rsp.valid)
  val fetched=BoringUtils.bore(if_stage_i.newInstruction)
  val instruction=if_stage_i.instr_rdata_id_o
  val d=floatDecoded.get
  val effect=intAccepted || accepted || id_stage_i.lsu_req_o || id_stage_i.csr_op_en_o || rf_we_wb_o || fp.io.write
  val current=FloatInstruction(instruction,cs_registers_i.fp_fcsr_o.get(7,5),cs_registers_i.fp_fs_o.get)
  val monitorPending=withClockAndReset(clk_i,(!rst_ni).asAsyncReset) { RegInit(false.B) }
  val monitorInstruction=withClockAndReset(clk_i,(!rst_ni).asAsyncReset) { RegInit(0.U(32.W)) }
  val monitorPc=withClockAndReset(clk_i,(!rst_ni).asAsyncReset) { RegInit(0.U(32.W)) }
  val monitorDestination=withClockAndReset(clk_i,(!rst_ni).asAsyncReset) { RegInit(0.U(5.W)) }
  val monitorWritesFloat=withClockAndReset(clk_i,(!rst_ni).asAsyncReset) { RegInit(false.B) }
  val monitorLoadFailed=withClockAndReset(clk_i,(!rst_ni).asAsyncReset) { RegInit(false.B) }
  withClockAndReset(clk_i,(!rst_ni).asAsyncReset) {
    when(accepted) {
      monitorPending:=true.B; monitorInstruction:=instruction; monitorPc:=if_stage_i.pc_id_o
      monitorDestination:=d.rd; monitorWritesFloat:=d.writeFloat
    }
    when(consumed || cancel) { monitorPending:=false.B }
    // Error history belongs to this issued load transaction. Unsolicited
    // responses before issue are not failures of a future instruction.
    when(id_stage_i.lsu_req_o) { monitorLoadFailed:=false.B }
    when((id_stage_i.lsu_req_o || id_stage_i.expecting_load_resp_o) &&
        (load_store_unit_i.load_err_o || load_store_unit_i.load_resp_intg_err_o)) { monitorLoadFailed:=true.B }
    when(id_stage_i.instr_valid_clear_o) { monitorLoadFailed:=false.B }
  }
  withClockAndReset(clk_i,false.B) {
    val previousClear=RegNext(id_stage_i.instr_valid_clear_o)
    val previousReset=RegNext(!rst_ni)
    when(checking && rst_ni) {
      if(coversOnly) {
        cover(accepted)
        cover(consumed && monitorWritesFloat && monitorDestination===0.U)
        cover(consumed && !monitorWritesFloat)
        cover(fp.io.commitLoad)
        cover(monitorPending && irq_timer_i)
        cover(monitorPending && debug_req_i)
        cover(id_stage_i.illegal_insn_o && current.recognized)
        cover(id_stage_i.csr_op_en_o)
      } else {
        assert(!accepted || !monitorPending)
        assert(!consumed || monitorPending)
        assert(!response || monitorPending)
        assert(!cancel || !consumed)
        assert(!fp.io.commitArithmetic || (response && !cancel))
        assert(!(fp.io.commitArithmetic && fp.io.commitLoad))
        assert(!fp.io.commitArithmetic || id_stage_i.instr_id_done_o)
        assert(!fp.io.commitLoad || id_stage_i.instr_id_done_o)
        assert(!(id_stage_i.instr_id_done_o && d.legal && d.arithmetic) || consumed)
        assert(!fp.io.commitLoad || (!monitorLoadFailed && !load_store_unit_i.load_err_o &&
          !load_store_unit_i.load_resp_intg_err_o && load_store_unit_i.lsu_rdata_valid_o))
        assert(!fp.io.write || fp.io.commitLoad || (consumed && monitorWritesFloat))
        assert(!consumed || !monitorWritesFloat || fp.io.writeAddress===monitorDestination)
        assert(cs_registers_i.fp_commit_i.get===(consumed || fp.io.commitLoad))
        assert(!fp.io.commitLoad || !rf_we_wb_o)
        assert(!(intAccepted && accepted))
        assert(!executionValid || Mux(d.legal && d.arithmetic,response,intResponse))
        assert(!id_stage_i.execute_consume_o.get || intConsumed || consumed)
        assert(!rf_we_wb_o || id_stage_i.execute_consume_o.get || integerLoadWrite)
        assert(!fetched || !if_stage_i.instr_valid_id_o || id_stage_i.instr_valid_clear_o)
        when(previousClear || previousReset) { assert(!d.legal && !d.recognized) }
        when(monitorPending) {
          assert(if_stage_i.instr_valid_id_o)
          assert(instruction===monitorInstruction && if_stage_i.pc_id_o===monitorPc)
        }
        assert(!(id_stage_i.csr_save_cause_o || id_stage_i.debug_csr_save_o ||
          id_stage_i.csr_restore_mret_id_o || id_stage_i.csr_restore_dret_id_o) || !monitorPending)
        when(effect) {
          assert(d.substitute===Mux(current.legal,current.substitute,instruction))
          assert(d.legal===current.legal && d.recognized===current.recognized)
        }
        when(accepted) {
          assert(d.rm===current.rm && d.op===current.op)
          assert(d.rs1===current.rs1 && d.rs2===current.rs2 && d.rs3===current.rs3 && d.rd===current.rd)
          assert(cs_registers_i.fp_fs_o.get=/=0.U)
        }
      }
    }
  }
}

object EmitFloatIntegrationFormal {
  def main(args:Array[String]):Unit={
    require(args.length==2)
    val output=Paths.get(args(0)).toAbsolutePath.normalize
    require(output.startsWith(Paths.get("build").toAbsolutePath.normalize))
    Files.createDirectories(output)
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new FloatIntegrationFormal(args(1)=="cover")),
      Array("--target-dir",output.toString),Array("--disable-all-randomization",
        "--verification-flavor=immediate","--lower-to-core","-strip-debug-info","--preserve-values=named"))
  }
}
