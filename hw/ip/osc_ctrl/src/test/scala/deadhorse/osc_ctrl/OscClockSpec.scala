package deadhorse.osc_ctrl

import chisel3._
import chisel3.simulator.{ChiselSim,Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class DividerProbe(fault: Boolean=false) extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val level=IO(Output(Bool()))
  val d=Module[OscDivider](if(fault) new OscDivider {
    override protected def terminal(v: Bool): Bool= !v
  } else new OscDivider)
  d.clk:=clk;d.reset_n:=reset_n;level:=d.divided.asBool
}

class OscClockSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan04/clock-simulation").toAbsolutePath
  }
  def divider(d: DividerProbe): Unit={
    d.reset_n.poke(false.B);d.clk.step(5);d.level.expect(false.B)
    var previous=false;var length=0;var validLow=false
    def sample(reset: Boolean): Unit={
      val before=d.level.peek().litToBoolean
      d.reset_n.poke((!reset).B)
      assert(d.level.peek().litToBoolean==before,"OSC_DIVIDER_OFF_EDGE")
      d.clk.step();val next=d.level.peek().litToBoolean
      if(next==previous) length+=1
      else {
        if(previous) assert(length==3,"OSC_DIVIDER_HIGH_WIDTH")
        else if(validLow) assert(length>=3,"OSC_DIVIDER_LOW_WIDTH")
        previous=next;length=1;validLow=true
      }
    }
    for(phase<-0 until 6) {
      for(_<-0 until 18+phase) sample(false)
      for(_<-0 until 5) sample(true)
    }
    // A free-running output has exactly three high, three low source periods.
    d.reset_n.poke(false.B);d.clk.step(5);d.reset_n.poke(true.B)
    for(edge<-1 to 36) {
      d.clk.step()
      assert(d.level.peek().litToBoolean==((edge/3)%2==1),"OSC_DIVIDER_RATIO")
    }
  }
  test("divide by six and complete high phases across reset at every phase") {
    simulateRaw(new DividerProbe)(divider)
  }
  test("wrong divider rejects the same pulse oracle") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new DividerProbe(true))(divider)
    }
    assert(e.getMessage.contains("OSC_DIVIDER_"))
  }
  test("stability counts actual source edges and starts afresh after oscillator off") {
    simulateRaw(new OscStability) {d=>
      d.reset_n.poke(false.B);d.oscillatorOn.poke(true.B);d.qualify.poke(false.B);d.count.poke(7.U)
      d.clk.step(4);d.reset_n.poke(true.B);d.clk.step(5)
      d.qualify.poke(true.B)
      for(_<-0 until 8) {d.clk.step();d.stable.expect(false.B)}
      d.clk.step(3);d.stable.expect(true.B)
      d.oscillatorOn.poke(false.B);d.stable.expect(false.B)
      d.qualify.poke(false.B);d.clk.step(3);d.oscillatorOn.poke(true.B);d.clk.step(5)
      d.stable.expect(false.B);d.qualify.poke(true.B);d.clk.step(11);d.stable.expect(true.B)
    }
  }
  test("local work cannot open an unauthorized source and closure follows the request") {
    val settings=Settings.defaultRaw[OscMainGate].withLibraryPaths(Seq(Paths.get(
      "hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
    simulateRaw(new OscMainGate,settings=settings,firtoolOpts=Array(
      "--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
      "--ckg-enable=en_i","--ckg-test-enable=test_en_i")) {d=>
      d.reset_n.poke(false.B);d.request.poke(false.B);d.verified.poke(false.B)
      d.command.poke(false.B);d.consume.poke(true.B)
      d.localHold.poke(true.B);d.coreIdle.poke(false.B);d.clk.step(4);d.reset_n.poke(true.B)
      d.clk.step(5);d.closed.expect(false.B)
      d.localHold.poke(false.B);d.coreIdle.poke(true.B);d.command.poke(true.B)
      d.clk.step();d.command.poke(false.B);d.clk.step(2);d.closed.expect(true.B)
      d.verified.poke(true.B);d.request.poke(true.B);d.clk.step(2);d.ready.expect(true.B)
      d.command.poke(true.B);d.clk.step();d.command.poke(false.B);d.clk.step(2);d.closed.expect(false.B)
      d.request.poke(false.B);d.command.poke(true.B);d.clk.step();d.command.poke(false.B)
      d.clk.step();d.closed.expect(false.B)
      d.clk.step(4);d.closed.expect(true.B)
    }
  }
}
