package deadhorse.osc_ctrl

import chisel3._
import chisel3.util._

/** Digital four-edge contract only; physical startup is an extracted obligation. */
class LfReadyFormal(early: Boolean=false) extends RawModule {
  val clock=IO(Input(Clock()));val power_n=IO(Input(Bool()));val enable=IO(Input(Bool()))
  val dut=Module[LfReadyPhysical](if(early) new LfReadyPhysical {
    override protected def qualifiedReady(third: Bool,fourth: Bool): Bool=third
  } else new LfReadyPhysical)
  dut.source:=clock;dut.power_n:=power_n;dut.enable:=enable
  val valid=power_n && enable
  withClockAndReset(clock,(!valid).asAsyncReset) {
    // Specification: record a history of valid observations, independently of
    // the implementation's two reset-release stages and two qualification flops.
    val history=RegInit(0.U(4.W));history:=Cat(history(2,0),true.B)
    assert(dut.ready===history.andR)
    cover(dut.ready)
  }
  withClockAndReset(clock,false.B) {assert(valid || !dut.ready)}
}

object EmitLfReadyFormal extends App {
  require(args.length==1)
  for(early<-Seq(false,true)) _root_.circt.stage.ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new LfReadyFormal(early)),
    Array("--target-dir",s"${args(0)}/${if(early) "early" else "correct"}"),
    Array("--disable-all-randomization","--strip-debug-info",
      "--verification-flavor=immediate","--lower-to-core"))
}
