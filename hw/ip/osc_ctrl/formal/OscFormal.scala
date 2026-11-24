package deadhorse.osc_ctrl

import chisel3._
import _root_.circt.stage.ChiselStage

/** No input protocol assumptions: arbitrary synchronized demands and source
  * reports. Composition must separately establish freshness of those reports. */
class OscFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val sleep=IO(Input(Bool()));val deep=IO(Input(Bool()));val forceRun=IO(Input(Bool()))
  val hold=IO(Input(Bool()));val oscHold=IO(Input(Bool()));val idle=IO(Input(Bool()))
  val closed=IO(Input(Bool()));val stable=IO(Input(Bool()));val wake=IO(Input(UInt(8.W)))
  val mask=IO(Input(UInt(8.W)))
  val delay=IO(Input(UInt(16.W)));val timeout=IO(Input(UInt(16.W)));val edges=IO(Input(UInt(16.W)))
  val d=Module[OscSequencer](variant match {
    case "wake"=>new OscSequencer {override protected def capturedWake(v: UInt): UInt=0.U}
    case "gate"=>new OscSequencer {override protected def gateAllowed(v: Bool): Bool=false.B}
    case "early_gate"=>new OscSequencer {override protected def gateOutput(v: Bool): Bool=true.B}
    case "reset"=>new OscSequencer {override protected def resetOn: Bool=false.B}
    case "hold"=>new OscSequencer {
      override protected def shutdownReady(v: Bool): Bool=true.B
      override protected def stopAllowed(v: Bool): Bool=true.B
    }
    case _=>new OscSequencer
  })
  d.clk:=clock;d.reset_n:=reset_n;d.sleep:=sleep;d.deep:=deep;d.forceRun:=forceRun
  d.mainHold:=hold;d.oscillatorHold:=oscHold;d.coreIdle:=idle;d.gateClosed:=closed
  d.stable:=stable;d.wake:=wake;d.wakeEnable:=mask
  d.delayTicks:=delay;d.timeoutTicks:=timeout;d.stableEdges:=edges
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val past=RegNext(true.B,false.B)
    val oldOn=RegNext(d.oscillatorOn,true.B)
    val oldHold=RegNext(hold || oscHold || forceRun,false.B)
    val oldIdle=RegNext(idle,false.B);val oldClosed=RegNext(closed,false.B)
    val oldPhase=RegNext(d.state,3.U)
    val oldWake=RegNext(wake & mask,0.U)
    val observed=RegInit(false.B)
    when(!d.oscillatorOn) {observed:=false.B}
      .elsewhen(d.qualify && stable) {observed:=true.B}
    if(variant=="cover") {
      cover(d.state===0.U && d.gateRequest)
      cover(!d.oscillatorOn)
      cover(d.lastWake.orR)
      cover(d.fault)
    } else {
      when(past && oldOn && !d.oscillatorOn) {
        assert(!oldHold && oldIdle && oldClosed && oldPhase===1.U)
      }
      assert(!d.gateRequest || d.oscillatorOn && observed)
      when(past) {assert(((d.pendingWake | d.lastWake) & oldWake)===oldWake)}
      assert(!d.fault || d.oscillatorOn && !d.gateRequest)
      assert(d.state=/=0.U || d.gateRequest)
    }
  }
  if(variant!="cover") withClockAndReset(clock,false.B) {
    assert(reset_n || d.oscillatorOn && !d.gateRequest)
  }
}

object EmitOscFormal extends App {
  require(args.length==1)
  for(v<-Seq("correct","wake","gate","early_gate","reset","hold","cover")) ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new OscFormal(v)),Array("--target-dir",s"${args(0)}/$v"),
    Array("--disable-all-randomization","--disable-opt","--lint-static-asserts=false",
      "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
