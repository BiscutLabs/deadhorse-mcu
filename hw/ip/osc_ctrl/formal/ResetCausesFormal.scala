package deadhorse.osc_ctrl

import chisel3._
import deadhorse.lib.{ResetRelease,CdcEpoch}

/** Independent raw-source observers; no DUT state or helper is assumed.
  * Pin edges are independent of AON, including pulses wholly between AON edges.
  * The six-bit epoch is used only by a 24-global-step cover (cannot wrap there).
  */
class ResetCausesFormal(bypass: Boolean, variant: String,shared: Boolean=false) extends RawModule {
  val aon=IO(Input(Clock()));val observe=IO(Input(Clock()))
  val supplyReset_n=IO(Input(Bool()));val externalReset_n=IO(Input(Bool()))
  val brownout=IO(Input(Bool()));val checkerInit_n=IO(Input(Bool()))
  val cold=if(bypass) externalReset_n else supplyReset_n
  val d=Module(new ResetCauses(qualifiedResets=shared))
  d.clk:=aon;d.coldReset_n:= (if(variant=="cold") true.B else cold)
  d.externalReset_n:= (if(variant=="pin") true.B else if(variant=="invent-pin") false.B else externalReset_n)
  d.brownout:= (if(variant=="brown") false.B else if(variant=="invent-brown") true.B else brownout)
  d.bypass:= (if(variant=="bypass") false.B else bypass.B)
  if(shared) {
    val a=Module(new ResetRelease);val b=Module(new ResetRelease)
    a.clk:=observe;b.clk:=aon;a.reset_n:=d.coldReset_n;b.reset_n:=d.coldReset_n
    val pin=Module(new CdcEpoch(rawCapture=true))
    pin.aClock:=observe;pin.bClock:=aon;pin.aReset_n:=a.released;pin.bReset_n:=b.released
    pin.cancel_n:=d.coldReset_n && d.externalReset_n
    d.releases.get.cold:=b.released;d.releases.get.pin:=pin.bLocal
  }
  val coldAge=withClockAndReset(aon,(!cold).asAsyncReset) {
    val n=RegInit(0.U(2.W));when(n<3.U) {n:=n+1.U};n
  }
  val pinReleased=withClockAndReset(externalReset_n.asClock,(!cold).asAsyncReset) {
    val seen=RegInit(false.B);when(coldAge>=2.U) {seen:=true.B};seen
  }
  val expectedPin=withClockAndReset(aon,(!cold).asAsyncReset) {
    val seen=RegInit(false.B)
    when(coldAge>=2.U && (!externalReset_n || pinReleased)) {seen:=true.B};seen
  }
  val expectedBrown=withClockAndReset(aon,(!cold).asAsyncReset) {
    val age=RegInit(0.U(2.W));val seen=RegInit(false.B)
    when(coldAge>=2.U && brownout) {
      when(age<3.U) {age:=age+1.U}
      when(age>=2.U) {seen:=true.B}
    }.otherwise {age:=0.U}
    seen
  }
  // Upper bounds observe only raw sources, independently of DUT cause bits.
  // Either edge records a pin pulse; current low also covers a pulse straddling
  // cold release before either edge has occurred in this cold epoch.
  val pinFell=withClockAndReset((!externalReset_n).asClock,(!cold).asAsyncReset) {
    val seen=RegInit(false.B);seen:=true.B;seen
  }
  val pinRose=withClockAndReset(externalReset_n.asClock,(!cold).asAsyncReset) {
    val seen=RegInit(false.B);seen:=true.B;seen
  }
  val brownSource=withClockAndReset(aon,(!cold).asAsyncReset) {
    val seen=RegInit(false.B);when(coldAge>=2.U && brownout) {seen:=true.B};seen
  }
  val everCause=withClockAndReset(observe,(!checkerInit_n).asAsyncReset) {
    val seen=RegInit(false.B)
    when(coldAge>=3.U && (if(bypass) true.B else d.causes(2,1).orR)) {seen:=true.B};seen
  }
  val epoch=withClockAndReset(aon,(!cold).asAsyncReset) {
    val n=RegInit(0.U(6.W));n:=n+1.U;n
  }
  val (fallEpoch,fallValid)=withClockAndReset((!externalReset_n).asClock,(!cold).asAsyncReset) {
    val n=RegInit(0.U(6.W));val valid=RegInit(false.B)
    n:=epoch;valid:=coldAge>=2.U && !aon.asBool;(n,valid)
  }
  val subedgePulse=withClockAndReset(externalReset_n.asClock,(!cold).asAsyncReset) {
    val seen=RegInit(false.B)
    when(fallValid && epoch===fallEpoch && coldAge>=2.U && !aon.asBool) {seen:=true.B};seen
  }
  // Observe the completed pulse before another AON rising edge. Checking only
  // the pin-edge flop's input permits coincident pin/AON edges in clk2fflogic.
  val observedSubedge=withClockAndReset(observe,(!cold).asAsyncReset) {
    val seen=RegInit(false.B)
    when(subedgePulse && externalReset_n && epoch===fallEpoch && !aon.asBool) {seen:=true.B};seen
  }
  withClockAndReset(observe,false.B) {
    assert(cold || d.causes===(if(bypass) 4.U else 1.U))
    if(bypass) {
      assert(d.causes===4.U)
      cover(coldAge>=3.U && brownout && d.causes===4.U)
      cover(everCause && !cold && d.causes===4.U)
    } else {
      assert(d.causes===1.U || d.causes===2.U || d.causes===5.U || d.causes===6.U)
      assert(!expectedPin || d.causes(2))
      assert(!expectedBrown || (d.causes(1) && !d.causes(0)))
      assert(!d.causes(2) || !externalReset_n || pinFell || pinRose)
      assert(!d.causes(1) || brownSource)
      cover(coldAge>=3.U && d.causes===1.U)
      cover(observedSubedge && d.causes===5.U)
      cover(expectedBrown && d.causes===2.U)
      cover(expectedBrown && expectedPin && d.causes===6.U)
      cover(everCause && !cold && d.causes===1.U)
    }
  }
  if(!bypass) withClockAndReset(aon,(!cold).asAsyncReset) {
    val pin=RegNext(d.causes(2),false.B);val brown=RegNext(d.causes(1),false.B)
    assert(!pin || d.causes(2));assert(!brown || d.causes(1))
  }
}

object EmitResetCausesFormal extends App {
  require(args.length==1 || args.length==2 && args(1)=="shared")
  for(bypass<-Seq(false,true);variant<- (if(bypass) Seq("correct","bypass") else Seq("correct","cold","pin","brown","invent-pin","invent-brown"))) {
    val name=s"${if(bypass) "bypass" else "normal"}-$variant"
    _root_.circt.stage.ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new ResetCausesFormal(bypass,variant,args.length==2)),
      Array("--target-dir",s"${args(0)}/$name"),Array("--disable-all-randomization","--disable-opt",
        "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
  }
}
