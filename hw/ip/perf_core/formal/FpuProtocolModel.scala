package deadhorse.perf_core

import chisel3._
import chisel3.util._
import deadhorse.fpu.{FpuRequest,FpuResponse}
import _root_.circt.stage.ChiselStage

/** Formal-only overapproximation of T12's proved single-outstanding protocol.
  * Completion latency and result/flags are unconstrained; no arithmetic claim.
  */
class FpuProtocolModel extends Module with RequireAsyncReset {
  override def desiredName="Fpu"
  val io=IO(new Bundle {
    val req=Flipped(Decoupled(new FpuRequest)); val rsp=Decoupled(new FpuResponse)
    val cancel=Input(Bool())
    val finish=Input(Bool()); val arbitrary=Input(new FpuResponse)
  })
  val pending=RegInit(false.B); val valid=RegInit(false.B)
  val response=RegInit(0.U.asTypeOf(new FpuResponse))
  val cleared=RegNext(io.cancel,true.B)
  io.req.ready:= !pending; io.rsp.valid:=valid
  // Invalid payloads are unconstrained except the proved reset/cancel zero.
  io.rsp.bits:=Mux(valid,response,Mux(cleared,0.U.asTypeOf(response),io.arbitrary))
  when(io.req.fire) { pending:=true.B }
  when(pending && !valid && io.finish) { response:=io.arbitrary; valid:=true.B }
  when(io.rsp.fire) { pending:=false.B; valid:=false.B }
  when(io.cancel) { pending:=false.B; valid:=false.B; response:=0.U.asTypeOf(response) }
}

object EmitFpuProtocolModel extends App {
  require(args.length==1)
  ChiselStage.emitSystemVerilogFile(new FpuProtocolModel,Array("--target-dir",args(0)),
    Array("--disable-all-randomization","--lower-to-core","-strip-debug-info","--preserve-values=named"))
}
