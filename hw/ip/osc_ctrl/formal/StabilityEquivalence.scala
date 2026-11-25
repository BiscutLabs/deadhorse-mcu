package deadhorse.osc_ctrl

import chisel3._

/** Same production state machine with the original arithmetic on the reference
  * side. Arbitrary requests/settings/reset: no bundled-data premise is needed
  * to prove the implementation change preserves every stable output cycle. */
class StabilityEquivalence(fault: Boolean=false,shared: Boolean=false) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val oscillatorOn=IO(Input(Bool()));val qualify=IO(Input(Bool()))
  val count=IO(Input(UInt(16.W)))
  val clear=if(shared) Some(IO(Input(Bool()))) else None
  val candidate=Module[OscStability](if(shared) new OscStability(qualifiedReset=true) {
    override protected def clearedReady: Bool=fault.B
  } else if(fault) new OscStability {
    override protected def decrement(value: UInt): UInt=value-2.U
  } else new OscStability)
  val reference=Module(new OscStability(qualifiedReset=shared) {
    override protected def decrement(value: UInt): UInt=if(shared) super.decrement(value) else value-1.U
    override protected def clearRemaining: Boolean=true
  })
  for(d<-Seq(candidate,reference)) {
    d.clk:=clock;d.reset_n:=reset_n;d.oscillatorOn:=oscillatorOn
    d.qualify:=qualify;d.count:=count
    d.clear.foreach(_:=clear.get)
  }
  withClockAndReset(clock,false.B) {
    assert(candidate.stable===reference.stable)
    if(shared) {
      val seenClear=withReset((!reset_n).asAsyncReset) {val v=RegInit(false.B);when(clear.get) {v:=true.B};v}
      cover(candidate.stable && seenClear)
    } else cover(candidate.stable)
  }
}

object EmitStabilityEquivalence extends App {
  require(args.length==1 || args.length==2 && args(1)=="shared")
  for(fault<-Seq(false,true)) _root_.circt.stage.ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new StabilityEquivalence(fault,args.length==2)),
    Array("--target-dir",s"${args(0)}/${if(fault) "fault" else "correct"}"),
    Array("--disable-all-randomization","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
