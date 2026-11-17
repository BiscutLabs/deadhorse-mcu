package deadhorse.bus_bridge

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException

class DirectionPermitTest(fault: Boolean) extends RawModule {
  val ac = IO(Input(Bool())); val mc = IO(Input(Bool()))
  val an = IO(Input(Bool())); val mn = IO(Input(Bool()))
  val a = IO(Input(Bool())); val m = IO(Input(Bool()))
  val pa = IO(Output(Bool())); val pm = IO(Output(Bool()))
  val d = Module(if (fault) new DirectionBadPermit else new DirectionPermit)
  d.aonClock := ac.asClock; d.mainClock := mc.asClock
  d.aonReset_n := an; d.mainReset_n := mn
  d.requestAon := a; d.requestMain := m
  pa := d.permitAon; pm := d.permitMain
}

class DirectionPermitSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t14/permit-simulation").toAbsolutePath
  }
  private def check(fault: Boolean): Unit = {
    simulateRaw(new DirectionPermitTest(fault), subdirectory = Some(if (fault) "early-reuse" else "correct")) { d =>
      def yes(b: Bool): Boolean = b.peek().litValue == 1
      def invariant(): Unit = assert(!(yes(d.pa) && yes(d.pm)), "PERMIT_MODEL_OVERLAP")
      d.ac.poke(false.B); d.mc.poke(false.B)
      d.an.poke(true.B); d.mn.poke(true.B); d.a.poke(false.B); d.m.poke(false.B)
      d.pa.peek(); d.an.poke(false.B); d.mn.poke(false.B); d.pa.peek()
      assert(!yes(d.pa) && !yes(d.pm))
      d.an.poke(true.B); d.mn.poke(true.B)
      var ticks = 0
      // Each driver tick contains an AON edge; main can be slower or stopped.
      def step(main: Boolean = true): Unit = {
        d.ac.poke(true.B); invariant()
        if (main) { d.mc.poke(true.B); invariant() }
        d.ac.poke(false.B); d.mc.poke(false.B); invariant(); ticks += 1
      }
      def until(message: String)(done: => Boolean): Unit = {
        var spent = 0
        while (!done && spent < 96) { step(main = ticks % 3 == 0); spent += 1 }
        assert(done, "PERMIT_MODEL_PROGRESS " + message)
      }
      for (_ <- 0 until 12) step()
      // Abstract reference: one owner; with both requests persistent, turns alternate.
      d.a.poke(true.B); d.m.poke(true.B)
      until("initial AON turn") { yes(d.pa) }
      for (_ <- 0 until 12) { step(); assert(yes(d.pa) && !yes(d.pm)) }
      d.a.poke(false.B)
      until("main turn after AON releases") { yes(d.pm) }
      d.a.poke(true.B)
      for (_ <- 0 until 12) { step(); assert(yes(d.pm) && !yes(d.pa)) }
      // Main withdrew after observing its permit. Its stopped clock cannot yet
      // observe revocation, so another owner must wait even though AON is running.
      d.m.poke(false.B)
      for (_ <- 0 until 24) { step(main = false); assert(yes(d.pm) && !yes(d.pa), "PERMIT_MODEL_EARLY_REUSE") }
      until("AON after main observes revocation") { yes(d.pa) }
      d.m.poke(true.B); d.a.poke(false.B)
      until("second main turn") { yes(d.pm) }
      // No-work withdrawal still completes all four handshake phases.
      d.m.poke(false.B)
      until("withdrawal acknowledgment") { !yes(d.pm) }
      d.m.poke(true.B)
      until("reacquire after observed low") { yes(d.pm) }
      // Each one-sided reset clears both permits without a clock edge.
      for (resetAon <- Seq(false, true)) {
        if (resetAon) d.an.poke(false.B) else d.mn.poke(false.B)
        d.pa.peek(); assert(!yes(d.pa) && !yes(d.pm), "PERMIT_MODEL_RESET")
        d.a.poke(false.B); d.m.poke(false.B)
        for (_ <- 0 until 5) step(main = false)
        if (resetAon) d.an.poke(true.B) else d.mn.poke(true.B)
        for (_ <- 0 until 12) step()
        d.a.poke(true.B)
        until("service after reset") { yes(d.pa) }
      }
    }
  }
  test("four-phase permits alternate without overlap across stopped clocks, withdrawal and reset") { check(false) }
  test("actual revocation-interlock fault is rejected by the same model") {
    val error = intercept[TestFailedException] { check(true) }
    assert(error.getMessage.contains("PERMIT_MODEL_OVERLAP") || error.getMessage.contains("PERMIT_MODEL_EARLY_REUSE"))
  }
}
