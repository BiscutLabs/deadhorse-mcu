package deadhorse.top

import chisel3._
import chisel3.simulator.{ChiselSim,Settings}
import chisel3.testing.HasTestingDirectory
import deadhorse.osc_ctrl._
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Real production source boundary and shared releases, without CPU traffic. */
class SocSourceEpochBench(losePin: Boolean=false) extends RawModule {
  val aon=IO(Input(Clock()));val source=IO(Input(Clock()))
  val cold=IO(Input(Bool()));val pin=IO(Input(Bool()));val warm=IO(Input(Bool()))
  val sleep=IO(Input(Bool()));val wake=IO(Input(UInt(8.W)))
  val on=IO(Output(Bool()));val up=IO(Output(Bool()));val usbUp=IO(Output(Bool()))
  val stable=IO(Output(Bool()));val gate=IO(Output(Bool()));val fault=IO(Output(Bool()))
  val mainEdges=IO(Output(UInt(32.W)));val phase=IO(Output(UInt(2.W)))
  val boundary=Module(new OscClockReset(consolidated=true))
  val domains=Module(new SocResetDomains {
    override protected def initializeValue(warm: Bool,pin: Bool): Bool=if(losePin) warm else super.initializeValue(warm,pin)
  })
  boundary.oscIn:=source;boundary.rcClock:=aon;boundary.aonClockIn:=aon
  boundary.externalReset_n:=pin;boundary.supplyReset_n:=cold
  boundary.aonClockSelect:=false.B;boundary.porBypass:=false.B
  domains.mainClock:=boundary.ungatedClock;domains.aonClock:=boundary.aonClock
  domains.sourceClock:=source;domains.scanClock:=aon
  domains.cold_n:=cold;domains.pin_n:=pin;domains.warm_n:=cold && pin && warm
  domains.aonQualified:=boundary.aonReset_n;domains.mainQualified:=boundary.serviceReset_n
  boundary.shared.get.coldMain:=domains.released.coldMain
  boundary.shared.get.coldAon:=domains.released.coldAon
  boundary.shared.get.coldSource:=domains.released.coldSource
  boundary.shared.get.pinAon:=domains.released.pinAon
  boundary.shared.get.initialize:=domains.released.warmInitialize
  val policy=Module(new OscSequencer(withEpochClear=true))
  policy.clk:=aon;policy.reset_n:=domains.released.coldAon
  policy.initialize.get:=domains.released.warmInitialize
  policy.clearAck.get:=boundary.clearAck.get;boundary.epochClear.get:=policy.epochClear.get
  policy.sleep:=sleep;policy.deep:=true.B;policy.forceRun:= !domains.released.warmAon
  policy.mainHold:=false.B;policy.oscillatorHold:=false.B;policy.coreIdle:=true.B
  policy.gateClosed:=boundary.closed;policy.stable:=boundary.stable
  policy.wake:=wake;policy.wakeEnable:=255.U
  policy.delayTicks:=6.U;policy.timeoutTicks:=200.U;policy.stableEdges:=5.U
  boundary.oscillatorOn:=policy.oscillatorOn;boundary.gateRequest:=policy.gateRequest
  boundary.authorized:=policy.authorized;boundary.qualify:=policy.qualify;boundary.count:=policy.count
  boundary.localHold:=false.B;boundary.coreIdle:=true.B
  on:=policy.oscillatorOn;gate:=policy.gateRequest;fault:=policy.fault;phase:=policy.state
  up:=domains.released.warmMain;usbUp:=boundary.usbServiceReset_n;stable:=boundary.stable
  withClockAndReset(boundary.mainClock,(!cold).asAsyncReset) {
    val edges=RegInit(0.U(32.W));edges:=edges+1.U;mainEdges:=edges
  }
}

class SocSourceEpochSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t41/source-epoch-simulation").toAbsolutePath
  }
  private val settings=Settings.defaultRaw[SocSourceEpochBench].withLibraryPaths(Seq(Paths.get(
    "hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
  private val gateOptions=Array("--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
    "--ckg-enable=en_i","--ckg-test-enable=test_en_i")
  def exercise(d: SocSourceEpochBench): Unit={
      def tick(n: Int=1): Unit=for(_<-0 until n) {d.source.step(60);d.aon.step()}
      def running(): Unit={tick(100);d.on.expect(true.B);d.gate.expect(true.B);d.fault.expect(false.B);d.stable.expect(true.B)}
      d.cold.poke(false.B);d.pin.poke(false.B);d.warm.poke(false.B)
      d.sleep.poke(false.B);d.wake.poke(0.U);tick(4)
      d.cold.poke(true.B);d.pin.poke(true.B);d.warm.poke(true.B)
      running();d.up.expect(true.B);d.usbUp.expect(true.B)
      d.warm.poke(false.B);d.up.expect(false.B);d.usbUp.expect(true.B)
      running();d.up.expect(false.B);d.usbUp.expect(true.B)
      // A pin pulse INSIDE held ndmreset must restart source qualification.
      d.pin.poke(false.B);d.usbUp.expect(false.B);d.pin.poke(true.B)
      tick(7);d.gate.expect(false.B,"PIN_DURING_WARM_REQUALIFICATION_LOST")
      running();d.up.expect(false.B);d.usbUp.expect(true.B,"USB_PIN_EPOCH_STUCK")
      d.warm.poke(true.B);tick(8);d.up.expect(true.B)
      d.sleep.poke(true.B);tick();d.sleep.poke(false.B)
      var n=0
      while(d.on.peek().litToBoolean && n<100) {tick();n+=1}
      assert(n<100,"DEEP_CLEAR_DID_NOT_COMPLETE");d.phase.expect(2.U)
      val stopped=d.mainEdges.peek().litValue
      d.aon.step(10);d.mainEdges.expect(stopped.U)
      d.wake.poke(1.U);d.aon.step();d.wake.poke(0.U);d.on.expect(true.B)
      running();d.up.expect(true.B)
      assert(d.mainEdges.peek().litValue>stopped,"MAIN_GATE_NEVER_REOPENED")
      for(duringStart<-Seq(false,true)) {
        d.sleep.poke(true.B);tick();d.sleep.poke(false.B)
        n=0;while(d.on.peek().litToBoolean && n<100) {tick();n+=1}
        assert(n<100,"RESET_SLEEP_SCENARIO");d.phase.expect(2.U)
        if(duringStart) {
          d.wake.poke(1.U);d.aon.step();d.wake.poke(0.U)
          d.on.expect(true.B);d.stable.expect(false.B)
        }
        d.warm.poke(false.B);d.up.expect(false.B)
        // The reset pulse is observed while the physical source is stopped.
        d.aon.step(10);d.on.expect(true.B);d.up.expect(false.B)
        running();d.up.expect(false.B)
        d.warm.poke(true.B);tick(8);d.up.expect(true.B)
      }
  }
  test("shared releases requalify warm and coalesced pin resets, preserving USB's separate epoch") {
    simulateRaw(new SocSourceEpochBench,settings=settings,firtoolOpts=gateOptions)(exercise)
  }
  test("a pin event lost inside held warm reset is rejected") {
    val e=intercept[Throwable] {
      simulateRaw(new SocSourceEpochBench(losePin=true),settings=settings,firtoolOpts=gateOptions)(exercise)
    }
    assert(Iterator.iterate(e)(_.getCause).takeWhile(_!=null)
      .exists(x=>Option(x.getMessage).exists(_.contains("PIN_DURING_WARM_REQUALIFICATION_LOST"))))
  }
}
