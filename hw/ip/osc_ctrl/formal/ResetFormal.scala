package deadhorse.osc_ctrl

import chisel3._
import chisel3.util._

/** Both oscillator inputs use the proof clock. This proves reset sequencing
  * and strap state, not analog clock switching or metastability. D84 bypass is
  * a static elaboration choice; both choices are checked. */
class ResetFormal(bypass: Boolean,variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val externalReset_n=IO(Input(Bool()))
  val supplyReset_n=IO(Input(Bool()));val selectExternal=IO(Input(Bool()))
  val d=Module[ResetBootstrap](variant match {
    case "cold"=>new ResetBootstrap {override protected def coldSource(v: Bool): Bool=true.B}
    case "strap"=>new ResetBootstrap {override protected def clockSelection(v: Bool,r: Bool): Bool=r}
    case "early"=>new ResetBootstrap {override protected def qualifiedRelease(v: Bool,r: Bool): Bool=r}
    case _=>new ResetBootstrap
  })
  d.rcClock:=clock;d.externalAonClock:=clock;d.externalReset_n:=externalReset_n
  d.supplyReset_n:=supplyReset_n;d.selectExternal:=selectExternal;d.bypassPor:=bypass.B
  val cold=if(bypass) externalReset_n else supplyReset_n
  val raw=externalReset_n && cold
  // The specification monitor uses the independently specified raw sources.
  withClockAndReset(clock,(!raw).asAsyncReset) {
    val elapsed=RegInit(0.U(4.W))
    when(elapsed<11.U) {elapsed:=elapsed+1.U}
    val frozen=RegNext(d.strapsFrozen,false.B)
    val selected=RegNext(d.selectedExternal,false.B)
    when(frozen) {assert(d.selectedExternal===selected)}
    assert(!d.aonReset_n || elapsed>=11.U)
    cover(d.aonReset_n && d.selectedExternal)
    cover(d.aonReset_n && !d.selectedExternal)
  }
  // Raw assertion and cold routing must hold even while functional reset is on.
  withClockAndReset(clock,false.B) {
    assert(d.coldReset_n===cold)
    assert(raw || !d.aonReset_n)
  }
}

object EmitResetFormal extends App {
  require(args.length==1)
  for(bypass<-Seq(false,true);variant<-Seq("correct","cold","strap","early")) {
    val name=s"${if(bypass) "bypass" else "normal"}-$variant"
    _root_.circt.stage.ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new ResetFormal(bypass,variant)),
      Array("--target-dir",s"${args(0)}/$name"),Array("--disable-all-randomization","--disable-opt",
        "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
  }
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new PorBootstrapInitial),
    Array("--target-dir",s"${args(0)}/por-initial"),Array("--disable-all-randomization","--disable-opt",
      "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
