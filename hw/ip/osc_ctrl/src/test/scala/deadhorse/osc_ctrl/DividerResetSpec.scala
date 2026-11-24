package deadhorse.osc_ctrl

import chisel3._
import chisel3.simulator.{ChiselSim,Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Passive observations of the production binding, plus a real CDC bypass. */
class DividerResetProbe extends OscClockReset {
  val sourceReset=IO(Output(Bool()));sourceReset:=dividerReset
  val rawReset=IO(Output(Bool()));rawReset:=bootstrap.aonReset_n
  val level=IO(Output(Bool()));level:=divider.divided.asBool
  val gatedLevel=IO(Output(Bool()));gatedLevel:=mainClock.asBool
}

class DividerResetSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t33/divider-reset-simulation").toAbsolutePath
  }
  private val settings=Settings.defaultRaw[DividerResetProbe].withLibraryPaths(Seq(Paths.get(
    "hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
  private val gate=Array("--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
    "--ckg-enable=en_i","--ckg-test-enable=test_en_i")
  def initialize(d: DividerResetProbe): Unit={
    d.externalReset_n.poke(false.B);d.supplyReset_n.poke(false.B)
    d.aonClockSelect.poke(false.B);d.porBypass.poke(false.B)
    d.oscillatorOn.poke(true.B);d.gateRequest.poke(false.B);d.authorized.poke(false.B)
    d.qualify.poke(false.B);d.count.poke(256.U);d.localHold.poke(false.B);d.coreIdle.poke(true.B)
    d.rcClock.step(4)
  }
  def release(d: DividerResetProbe): Unit={
    d.supplyReset_n.poke(true.B);d.externalReset_n.poke(true.B);d.rcClock.step(16)
    d.rawReset.expect(true.B)
  }
  def exercise(d: DividerResetProbe): Unit={
    initialize(d);d.oscIn.step(8);d.sourceReset.expect(false.B);d.level.expect(false.B)
    release(d)
    assert(!d.sourceReset.peek().litToBoolean,"DIVIDER_RESET_UNSYNCHRONIZED")
    d.oscIn.step();d.sourceReset.expect(false.B)
    d.oscIn.step();d.sourceReset.expect(true.B)
    for(phase<-0 until 6) {
      d.oscIn.step(18+phase)
      val before=d.level.peek().litToBoolean
      d.externalReset_n.poke(false.B);d.rawReset.expect(false.B)
      d.level.expect(before.B)
      assert(d.sourceReset.peek().litToBoolean,"DIVIDER_RESET_UNSYNCHRONIZED")
      d.oscIn.step();d.sourceReset.expect(true.B)
      d.oscIn.step();d.sourceReset.expect(false.B)
      d.oscIn.step(6);d.level.expect(false.B)
      release(d);d.sourceReset.expect(false.B);d.oscIn.step(2);d.sourceReset.expect(true.B)
    }
  }
  test("production divider reset data synchronizes both transitions") {
    simulateRaw(new DividerResetProbe,settings=settings,firtoolOpts=gate)(exercise)
  }
  test("actual raw reset bypass fails the same transfer oracle") {
    val error=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new DividerResetProbe {
        override protected def dividerResetValue(local: Bool,raw: Bool): Bool=raw
      },settings=settings,firtoolOpts=gate)(exercise)
    }
    assert(error.getMessage.contains("DIVIDER_RESET_UNSYNCHRONIZED"))
  }
  test("source absent for the complete reset interval converges before authorization") {
    simulateRaw(new DividerResetProbe,settings=settings,firtoolOpts=gate) {d=>
      initialize(d);release(d) // No source edge has occurred, including during reset.
      // Arbitrary initialization is allowed; the monitor waits for convergence.
      for(_<-0 until 12) {d.oscIn.step();d.serviceReset_n.expect(false.B)}
      d.sourceReset.expect(true.B)
      var old=d.level.peek().litToBoolean;var age=0;var seen=false;var transitions=0
      for(_<-0 until 36) {
        d.oscIn.step();d.gatedLevel.expect(false.B)
        val next=d.level.peek().litToBoolean;age+=1
        if(next!=old) {
          if(seen) assert(age==3,"DIVIDER_RESET_RESTART_RATIO")
          seen=true;transitions+=1;age=0;old=next
        }
      }
      assert(transitions==12,"DIVIDER_RESET_RESTART_PROGRESS")
    }
  }
}
