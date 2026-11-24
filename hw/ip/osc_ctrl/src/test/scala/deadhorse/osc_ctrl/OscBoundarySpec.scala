package deadhorse.osc_ctrl

import chisel3._
import chisel3.simulator.{ChiselSim,Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class OscBoundaryProbe(bypassGate: Boolean=false,retainedEpoch: Boolean=false) extends RawModule {
  val osc=IO(Input(Clock()));val aon=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val on=IO(Input(Bool()));val authorize=IO(Input(Bool()));val request=IO(Input(Bool()))
  val qualify=IO(Input(Bool()));val hold=IO(Input(Bool()));val idle=IO(Input(Bool()))
  val stable=IO(Output(Bool()));val closed=IO(Output(Bool()));val ready=IO(Output(Bool()))
  val services=IO(Output(Bool()));val level=IO(Output(Bool()));val retained=IO(Output(UInt(16.W)))
  val d=Module(new OscClockReset {
    override protected def epochReset(q: Bool,b: Bool): Bool=if(retainedEpoch) b else q
    override protected def makeGate(): OscMainGate=if(bypassGate) new OscMainGate {
      override protected def gateEnable(v: Bool): Bool=v || localHold
    } else new OscMainGate
  })
  d.oscIn:=osc;d.rcClock:=aon;d.aonClockIn:=aon
  d.externalReset_n:=reset_n;d.supplyReset_n:=reset_n;d.porBypass:=false.B;d.aonClockSelect:=false.B
  d.oscillatorOn:=on;d.authorized:=authorize;d.gateRequest:=request;d.qualify:=qualify;d.count:=5.U
  d.localHold:=hold;d.coreIdle:=idle
  stable:=d.stable;closed:=d.closed;ready:=d.aonReset_n;services:=d.serviceReset_n;level:=d.mainClock.asBool
  withClockAndReset(d.mainClock,(!d.serviceReset_n).asAsyncReset) {
    val state=RegInit(0.U(16.W));state:=state+1.U;retained:=state
  }
}

class OscBoundarySpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan04/boundary-simulation").toAbsolutePath
  }
  private val settings=Settings.defaultRaw[OscBoundaryProbe].withLibraryPaths(Seq(Paths.get(
    "hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
  private val gate=Array("--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
    "--ckg-enable=en_i","--ckg-test-enable=test_en_i")
  def exercise(d: OscBoundaryProbe): Unit={
    def ticks(n: Int): Unit=for(_<-0 until n) {d.osc.step(12);d.aon.step()}
    d.reset_n.poke(false.B);d.on.poke(true.B);d.authorize.poke(false.B);d.request.poke(false.B)
    d.qualify.poke(false.B);d.hold.poke(true.B);d.idle.poke(false.B);ticks(4)
    d.reset_n.poke(true.B);ticks(16);d.ready.expect(true.B);d.services.expect(false.B)
    d.qualify.poke(true.B);ticks(6);d.stable.expect(true.B)
    assert(!d.level.peek().litToBoolean,"EARLY_EPOCH_CLOCK")
    d.authorize.poke(true.B);d.request.poke(true.B);ticks(8)
    d.services.expect(true.B);assert(d.retained.peek().litValue>0)
    d.hold.poke(false.B);d.idle.poke(true.B);d.request.poke(false.B);ticks(8)
    d.closed.expect(true.B);val saved=d.retained.peek().litValue
    d.authorize.poke(false.B);d.qualify.poke(false.B);d.on.poke(false.B)
    d.aon.step(8);d.services.expect(true.B);d.retained.expect(saved.U)
    // Pending work at restart must not consume the old epoch's authorization.
    d.hold.poke(true.B);d.idle.poke(false.B);d.on.poke(true.B)
    for(_<-0 until 48) {
      d.osc.step()
      assert(!d.level.peek().litToBoolean,"EARLY_EPOCH_CLOCK")
      d.retained.expect(saved.U)
    }
    d.aon.step(3);d.qualify.poke(true.B);ticks(6);d.stable.expect(true.B)
    d.authorize.poke(true.B);d.request.poke(true.B);ticks(8)
    assert(d.retained.peek().litValue>saved,"RETAINED_STATE_LOST")
    d.reset_n.poke(false.B);d.services.expect(false.B);d.ready.expect(false.B);d.retained.expect(0.U)
  }
  test("qualified startup and deep wake preserve state and prohibit early gate pulses") {
    simulateRaw(new OscBoundaryProbe,settings=settings,firtoolOpts=gate)(exercise)
  }
  test("local-demand gate bypass is rejected before authorization") {
    val failure=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new OscBoundaryProbe(true),settings=settings,firtoolOpts=gate)(exercise)
    }
    assert(failure.getMessage.contains("EARLY_EPOCH_CLOCK"))
  }
  test("FIFO epoch reset contains the former gate-reset-only fault") {
    simulateRaw(new OscBoundaryProbe(retainedEpoch=true),settings=settings,firtoolOpts=gate)(exercise)
  }
  test("busy close rejection permits cancellation without a future WFI") {
    simulateRaw(new OscBoundaryProbe,settings=settings,firtoolOpts=gate) {d=>
      def ticks(n: Int): Unit=for(_<-0 until n) {d.osc.step(12);d.aon.step()}
      d.reset_n.poke(false.B);d.on.poke(true.B);d.authorize.poke(false.B);d.request.poke(false.B)
      d.qualify.poke(false.B);d.hold.poke(true.B);d.idle.poke(false.B);ticks(4)
      d.reset_n.poke(true.B);ticks(16);d.qualify.poke(true.B);ticks(6)
      d.authorize.poke(true.B);d.request.poke(true.B);ticks(8)
      val first=d.retained.peek().litValue
      // Local work remains active throughout both the close and its cancel.
      d.request.poke(false.B)
      for(_<-0 until 32) {ticks(1);d.closed.expect(false.B)}
      val second=d.retained.peek().litValue
      d.request.poke(true.B)
      for(_<-0 until 32) {ticks(1);d.closed.expect(false.B)}
      assert(second>first && d.retained.peek().litValue>second,"CANCEL_REQUIRES_FUTURE_WFI")
      // Adjacent desired-level changes must not accept an earlier completion.
      d.hold.poke(false.B);d.idle.poke(true.B)
      d.request.poke(false.B);ticks(1);d.request.poke(true.B);ticks(1)
      d.request.poke(false.B);ticks(32);d.closed.expect(true.B)
      val saved=d.retained.peek().litValue;ticks(8);d.retained.expect(saved.U)
      d.request.poke(true.B);ticks(32)
      assert(d.retained.peek().litValue>saved,"REOPEN_COMPLETION_LOST")
    }
  }
}
