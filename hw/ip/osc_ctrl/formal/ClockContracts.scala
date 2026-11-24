package deadhorse.osc_ctrl

import chisel3._
import chisel3.util.experimental.BoringUtils

/** A transfer oracle and an elapsed-edge specification, separate from the
  * implementation's down-counter. All external inputs/clocks are arbitrary. */
class CountContract(variant: String) extends RawModule {
  val aon=IO(Input(Clock()));val source=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val on=IO(Input(Bool()));val qualify=IO(Input(Bool()));val count=IO(Input(UInt(16.W)))
  val d=Module[OscClockReset](variant match {
    case "data"=>new OscClockReset {override protected def configurationValue(v: UInt): UInt=v ^ 1.U}
    case "early"=>new OscClockReset {
      override protected def makeCounter(): OscStability=new OscStability {
        override protected def decrement(v: UInt): UInt=1.U(16.W)
      }
    }
    case _=>new OscClockReset
  })
  d.oscIn:=source;d.rcClock:=aon;d.aonClockIn:=aon
  d.aonClockSelect:=false.B;d.porBypass:=false.B
  d.externalReset_n:=reset_n;d.supplyReset_n:=reset_n
  d.oscillatorOn:=on;d.qualify:=qualify;d.count:=count
  d.authorized:=false.B;d.gateRequest:=false.B;d.localHold:=false.B;d.coreIdle:=true.B
  val writeUp=BoringUtils.bore(d.configuration.writeUp)
  val accepted=BoringUtils.bore(d.configuration.push) && BoringUtils.bore(d.configuration.ready)
  val valid=BoringUtils.bore(d.configuration.valid)
  val received=BoringUtils.bore(d.counter.count)
  val stable=BoringUtils.bore(d.counter.stable)
  val expected=withClockAndReset(aon,(!writeUp).asAsyncReset) {
    val value=RegInit(0.U(16.W))
    when(accepted) {value:=count}
    value
  }
  withClockAndReset(source,(!(d.aonReset_n && on)).asAsyncReset) {
    val elapsed=RegInit(0.U(16.W))
    when(valid && elapsed=/=65535.U) {elapsed:=elapsed+1.U}
    val wasValid=RegNext(valid,false.B);val prior=RegNext(received,0.U)
    assert(!valid || received===expected)
    when(wasValid && valid) {assert(received===prior)}
    // Qualification may take longer for CDC and capture, but never fewer
    // source edges than the accepted nonzero count (zero requests one edge).
    assert(!stable || valid && elapsed>=Mux(expected===0.U,1.U,expected))
    cover(stable && expected===9.U)
    cover(stable && expected===0.U)
  }
}

class GateClosureContract(fault: Boolean) extends RawModule {
  val source=IO(Input(Clock()));val observe=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val request=IO(Input(Bool()));val verified=IO(Input(Bool()));val hold=IO(Input(Bool()));val idle=IO(Input(Bool()))
  val command=IO(Input(Bool()));val consume=IO(Input(Bool()))
  val d=Module[OscMainGate](if(fault) new OscMainGate {
    override protected def closure(v: Bool): Bool=true.B
  } else new OscMainGate)
  d.clk:=source;d.reset_n:=reset_n;d.request:=request;d.verified:=verified;d.localHold:=hold;d.coreIdle:=idle
  d.command:=command;d.consume:=consume
  withClockAndReset(observe,(!reset_n).asAsyncReset) {
    assert(!d.closed || !d.gated.asBool)
    cover(d.closed)
    cover(d.gated.asBool)
  }
}

object EmitClockContracts extends App {
  require(args.length==1)
  val options=Array("--disable-all-randomization","--disable-opt","--strip-debug-info",
    "--verification-flavor=immediate","--lower-to-core",
    "--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
    "--ckg-enable=en_i","--ckg-test-enable=test_en_i")
  for(v<-Seq("correct","data","early")) _root_.circt.stage.ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new CountContract(v)),Array("--target-dir",s"${args(0)}/count-$v"),options)
  for(v<-Seq(false,true)) _root_.circt.stage.ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new GateClosureContract(v)),Array("--target-dir",s"${args(0)}/gate-${if(v) "fault" else "correct"}"),options)
}
