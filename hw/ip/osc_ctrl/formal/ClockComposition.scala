package deadhorse.osc_ctrl

import chisel3._
import deadhorse.lib.CdcSync

/** Actual source/AON clocks, synchronizers, divider and shared gate. No clock
  * ratio, fairness, running-source or synchronized-input assumption is made.
  * The monitor records an AON observation in the current oscillator epoch;
  * it does not read the gate's internal authorization state. */
class ClockComposition(variant: String) extends RawModule {
  val aon=IO(Input(Clock()));val source=IO(Input(Clock()))
  val reset_n=IO(Input(Bool()))
  val sleep=IO(Input(Bool()));val deep=IO(Input(Bool()));val forceRun=IO(Input(Bool()))
  val hold=IO(Input(Bool()));val oscillatorHold=IO(Input(Bool()));val idle=IO(Input(Bool()))
  // Independent arbitrary policy/local observations include all delayed CDC
  // relationships without assuming instantaneous delivery to AON.
  val localHold=IO(Input(Bool()));val localIdle=IO(Input(Bool()))
  val wake=IO(Input(UInt(8.W)));val mask=IO(Input(UInt(8.W)))
  val delay=IO(Input(UInt(16.W)));val timeout=IO(Input(UInt(16.W)));val edges=IO(Input(UInt(16.W)))
  val boundary=Module[OscClockReset](if(variant=="reset-contained") new OscClockReset {
    override protected def epochReset(q: Bool,b: Bool): Bool=b
  } else if(variant=="hold-fault") new OscClockReset {
    override protected def makeGate(): OscMainGate=new OscMainGate {
      override protected def workActive: Bool= !coreIdle
    }
  } else if(variant=="early" || variant=="stale") new OscClockReset {
    override protected def makeGate(): OscMainGate=new OscMainGate {
      // Direct final-enable faults remain effective after command ordering
      // makes authorization-only and gate-reset-only mutations redundant.
      override protected def gateEnable(v: Bool): Bool=if(variant=="early") true.B else v || localHold
    }
  } else new OscClockReset)
  val policy=Module(new OscSequencer)
  boundary.oscIn:=source;boundary.rcClock:=aon;boundary.aonClockIn:=aon
  boundary.aonClockSelect:=false.B;boundary.porBypass:=false.B
  boundary.externalReset_n:=reset_n;boundary.supplyReset_n:=reset_n
  policy.clk:=boundary.aonClock;policy.reset_n:=boundary.aonReset_n
  policy.sleep:=sleep;policy.deep:=deep;policy.mainHold:=hold;policy.forceRun:=forceRun
  policy.oscillatorHold:=oscillatorHold;policy.coreIdle:=idle
  policy.wake:=wake;policy.wakeEnable:=mask
  policy.delayTicks:=delay;policy.timeoutTicks:=timeout;policy.stableEdges:=edges
  policy.gateClosed:=boundary.closed;policy.stable:=boundary.stable
  boundary.oscillatorOn:=policy.oscillatorOn;boundary.gateRequest:=policy.gateRequest
  boundary.authorized:=policy.authorized
  boundary.qualify:=policy.qualify;boundary.count:=policy.count
  boundary.localHold:=localHold;boundary.coreIdle:=localIdle

  val observed=withClockAndReset(aon,(!(boundary.aonReset_n && policy.oscillatorOn)).asAsyncReset) {
    val seen=RegInit(false.B)
    when(policy.qualify && boundary.stable) {seen:=true.B}
    seen
  }
  // A reset may finish an existing high pulse. This checks each new active
  // main edge while the domain is out of reset, rather than truncating it.
  withClockAndReset(boundary.mainClock,(!boundary.aonReset_n).asAsyncReset) {
    assert(observed)
    assert(policy.oscillatorOn)
    cover(observed && boundary.serviceReset_n)
  }
  withClockAndReset(aon,(!boundary.aonReset_n).asAsyncReset) {
    val stopped=RegInit(false.B)
    when(!policy.oscillatorOn) {stopped:=true.B}
    cover(stopped && policy.state===0.U && observed)
    cover(policy.fault)
  }
}

/** Local demand may change on any actual main edge. This includes arbitrary
  * main-domain activity, then retains it while main is gated, as production's
  * registered hold does. AON demand remains independently arbitrary. */
class ClosureComposition(variant: String) extends ClockComposition(variant) {
  val observe=IO(Input(Clock()))
  val registeredHold=withClockAndReset(boundary.mainClock,(!boundary.aonReset_n).asAsyncReset) {
    RegNext(localHold,false.B)
  }
  def synchronized(value: Bool): Bool={
    val s=Module(new CdcSync(1));s.clk:=aon;s.reset_n:=boundary.aonReset_n;s.in:=value.asUInt;s.out.asBool
  }
  // Core idle is deliberately live/arbitrary: its production cone includes
  // reset, interrupt and debug contributions, not merely a main-clock flop.
  boundary.localHold:=registeredHold;boundary.coreIdle:=localIdle
  policy.mainHold:=hold || synchronized(registeredHold)
  policy.coreIdle:=synchronized(localIdle)
  if(variant=="closure-fault") policy.gateClosed:= !policy.gateRequest
  withClockAndReset(observe,(!boundary.aonReset_n).asAsyncReset) {
    // New demand during OFF is legal. The source must already have been gated
    // before OSC_EN falls; this observation catches a residual active pulse.
    assert(policy.oscillatorOn || !boundary.mainClock.asBool)
    assert(policy.oscillatorOn || !registeredHold)
    cover(!policy.oscillatorOn)
  }
}

object EmitClockComposition extends App {
  require(args.length==1 || args.length==2 && args(1)=="closure")
  val closure=args.length==2
  for(v<- (if(closure) Seq("correct","closure-fault","hold-fault") else Seq("correct","stale","early"))) _root_.circt.stage.ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(if(closure) new ClosureComposition(v) else new ClockComposition(v)),Array("--target-dir",s"${args(0)}/$v"),
    Array("--disable-all-randomization","--disable-opt","--strip-debug-info",
      "--verification-flavor=immediate","--lower-to-core",
      "--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
      "--ckg-enable=en_i","--ckg-test-enable=test_en_i"))
}
