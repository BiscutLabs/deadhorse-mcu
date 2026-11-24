package deadhorse.osc_ctrl

import chisel3._

/** Same production state machine with the original arithmetic on the reference
  * side. Arbitrary requests/settings/reset: no bundled-data premise is needed
  * to prove the implementation change preserves every stable output cycle. */
class StabilityEquivalence(fault: Boolean=false) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val oscillatorOn=IO(Input(Bool()));val qualify=IO(Input(Bool()))
  val count=IO(Input(UInt(16.W)))
  val candidate=Module[OscStability](if(fault) new OscStability {
    override protected def decrement(value: UInt): UInt=value-2.U
  } else new OscStability)
  val reference=Module(new OscStability {
    override protected def decrement(value: UInt): UInt=value-1.U
  })
  for(d<-Seq(candidate,reference)) {
    d.clk:=clock;d.reset_n:=reset_n;d.oscillatorOn:=oscillatorOn
    d.qualify:=qualify;d.count:=count
  }
  withClockAndReset(clock,false.B) {
    assert(candidate.stable===reference.stable)
    cover(candidate.stable)
  }
}

object EmitStabilityEquivalence extends App {
  require(args.length==1)
  for(fault<-Seq(false,true)) _root_.circt.stage.ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new StabilityEquivalence(fault)),
    Array("--target-dir",s"${args(0)}/${if(fault) "fault" else "correct"}"),
    Array("--disable-all-randomization","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
