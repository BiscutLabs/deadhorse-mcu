package deadhorse.power_reset

import chisel3._
import deadhorse.lib._

/** Atomic selector contract at the generated-register/control boundary.
  * No bus, origin, key or reset-release input assumption is added. The existing
  * RegBlock proof covers its hardware pulse contract; MMIO simulation separately
  * checks production address/origin/byte-strobe behavior. */
class PowerResetFormal(fault: Boolean) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val apply=IO(Input(Bool()));val selection=IO(Input(UInt(2.W)));val keyData=IO(Input(UInt(32.W)))
  val d=Module(new BrownoutSelect {
    override protected def acceptKey(value: Bool): Bool=if(fault) true.B else value
  })
  d.clk:=clock;d.reset_n:=reset_n;d.apply:=apply;d.selection:=selection;d.key:=keyData
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val past=RegNext(true.B,false.B)
    val old=RegNext(d.threshold,0.U)
    val key=RegNext(apply && keyData==="h42524f57".U && selection<2.U,false.B)
    val selected=RegNext(selection,0.U)
    val bad=RegNext(apply && (keyData=/="h42524f57".U || selection>=2.U),false.B)
    assert(d.threshold<2.U)
    when(past) {
      assert(d.threshold===Mux(key,selected,old))
      assert(d.invalid===bad)
    }
    cover(d.threshold===1.U)
    cover(old===1.U && d.threshold===0.U)
  }
  withClockAndReset(clock,false.B) {assert(reset_n || d.threshold===0.U)}
}

class ResetDemandFormal(injectFault: Boolean) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val forced=IO(Input(Bool()));val sleep=IO(Input(Bool()));val deep=IO(Input(Bool()))
  val stable=IO(Input(Bool()));val closed=IO(Input(Bool()));val hold=IO(Input(Bool()))
  val oscillatorHold=IO(Input(Bool()))
  val idle=IO(Input(Bool()));val wake=IO(Input(UInt(8.W)));val mask=IO(Input(UInt(8.W)))
  val d=Module(new deadhorse.osc_ctrl.OscSequencer {
    override protected def forcedRun(value: Bool): Bool=if(injectFault) false.B else value
  })
  d.clk:=clock;d.reset_n:=reset_n;d.forceRun:=forced;d.sleep:=sleep;d.deep:=deep
  d.mainHold:=hold;d.oscillatorHold:=oscillatorHold;d.coreIdle:=idle;d.stable:=stable;d.gateClosed:=closed
  d.wake:=wake;d.wakeEnable:=mask
  // These are unconstrained production-width settings, not shortened counters.
  val delay=IO(Input(UInt(16.W)));val timeout=IO(Input(UInt(16.W)));val edges=IO(Input(UInt(16.W)))
  d.delayTicks:=delay;d.timeoutTicks:=timeout;d.stableEdges:=edges
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val past=RegNext(true.B,false.B);val force=RegNext(forced,false.B)
    val phase=RegNext(d.state,3.U);val on=RegNext(d.oscillatorOn,true.B)
    when(past && force) {
      assert(d.oscillatorOn)
      when(phase===0.U || phase===1.U || phase===2.U && on) {
        assert(d.state===0.U && d.gateRequest)
      }
      when(phase===2.U && !on) {assert(d.state===3.U && !d.gateRequest)}
    }
    cover(past && force && phase===2.U && !on && d.oscillatorOn)
    cover(past && force && phase===1.U && d.state===0.U)
  }
}

object EmitPowerResetFormal extends App {
  require(args.length==2)
  for((name,make)<-Seq[(String,()=>RawModule)](
    "selector"->(()=>new PowerResetFormal(false)),
    "selector-fault"->(()=>new PowerResetFormal(true)),
    "demand"->(()=>new ResetDemandFormal(false)),
    "demand-fault"->(()=>new ResetDemandFormal(true)))) {
    _root_.circt.stage.ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(make()),
      Array("--target-dir",s"${args(1)}/$name"),Array("--disable-all-randomization",
        "--disable-opt","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
  }
}
