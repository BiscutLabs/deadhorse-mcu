package deadhorse.perf_core

import chisel3._
import chisel3.util._
import deadhorse.fpu.{FpuRequest,FpuResponse}
import _root_.circt.stage.ChiselStage

/** Formal-only protocol overapproximation with independent payload choices.
  * Invalid current payload must not constrain the next completion payload.
  * Latency, arithmetic result and flags are unrestricted.
  */
class FpuProtocolModelWide extends Module with RequireAsyncReset {
  override def desiredName = "Fpu"
  val io = IO(new Bundle {
    val req = Flipped(Decoupled(new FpuRequest))
    val rsp = Decoupled(new FpuResponse)
    val cancel = Input(Bool())
    val finish = Input(Bool())
    val invalidPayload = Input(new FpuResponse)
    val completionPayload = Input(new FpuResponse)
  })
  val pending = RegInit(false.B)
  val valid = RegInit(false.B)
  val response = RegInit(0.U.asTypeOf(new FpuResponse))
  val cleared = RegNext(io.cancel,true.B)
  io.req.ready := !pending
  io.rsp.valid := valid
  io.rsp.bits := Mux(valid,response,Mux(cleared,0.U.asTypeOf(response),io.invalidPayload))
  when(io.req.fire) { pending := true.B }
  when(pending && !valid && io.finish) { response := io.completionPayload; valid := true.B }
  when(io.rsp.fire) { pending := false.B; valid := false.B }
  when(io.cancel) { pending := false.B; valid := false.B; response := 0.U.asTypeOf(response) }
}

object EmitFpuProtocolModelWide extends App {
  require(args.length == 1)
  ChiselStage.emitSystemVerilogFile(new FpuProtocolModelWide,Array("--target-dir",args(0)),
    Array("--disable-all-randomization","--lower-to-core","-strip-debug-info","--preserve-values=named"))
}
