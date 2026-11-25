package deadhorse.osc_ctrl

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Independent source peers deliberately delay each acknowledgement. */
class OscEpochClearSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t41/osc-epoch-clear").toAbsolutePath
  }
  def initialize(d: OscSequencer): Unit={
    d.reset_n.poke(false.B);d.initialize.get.poke(false.B);d.clearAck.get.poke(0.U)
    d.sleep.poke(false.B);d.deep.poke(true.B);d.forceRun.poke(false.B)
    d.mainHold.poke(false.B);d.oscillatorHold.poke(false.B);d.coreIdle.poke(true.B)
    d.gateClosed.poke(false.B);d.stable.poke(false.B);d.wake.poke(0.U);d.wakeEnable.poke(255.U)
    d.delayTicks.poke(3.U);d.timeoutTicks.poke(24.U);d.stableEdges.poke(5.U)
    d.clk.step(2);d.reset_n.poke(true.B);d.clk.step()
  }
  def qualify(d: OscSequencer): Unit={
    d.clearAck.get.poke(1.U);d.clk.step(2)
    d.epochClear.get.expect(true.B,"SOURCE_CLEAR_ACK_REQUIRED")
    d.gateRequest.expect(false.B);d.oscillatorOn.expect(true.B)
    d.clearAck.get.poke(3.U);d.clk.step();d.epochClear.get.expect(false.B)
    d.clearAck.get.poke(1.U);d.clk.step(2);d.qualify.expect(false.B)
    d.clearAck.get.poke(0.U);d.stable.poke(false.B)
    d.clk.step(3);d.qualify.expect(true.B);d.gateRequest.expect(false.B)
    d.stable.poke(true.B);d.clk.step();d.gateRequest.expect(true.B);d.authorized.expect(true.B)
  }
  def stop(d: OscSequencer): Unit={
    d.sleep.poke(true.B);d.clk.step();d.sleep.poke(false.B);d.clk.step(2)
    d.gateRequest.expect(false.B);d.gateClosed.poke(true.B);d.clk.step()
    d.epochClear.get.expect(true.B);d.authorized.expect(false.B)
  }
  test("deep OFF waits for both source clears; wake during clearing starts a fresh epoch") {
    simulateRaw(new OscSequencer(withEpochClear=true)) {d=>
      initialize(d);qualify(d);stop(d)
      d.clearAck.get.poke(1.U);d.clk.step(4);d.oscillatorOn.expect(true.B)
      d.wake.poke(32.U);d.clk.step();d.wake.poke(0.U);d.state.expect(3.U)
      d.oscillatorOn.expect(true.B);d.gateRequest.expect(false.B)
      d.gateClosed.poke(false.B);qualify(d);d.clk.step();d.lastWake.expect(32.U)
      stop(d);d.clearAck.get.poke(3.U);d.clk.step()
      d.oscillatorOn.expect(false.B);d.epochClear.get.expect(true.B);d.state.expect(2.U)
      d.clk.step(8);d.epochClear.get.expect(true.B);d.oscillatorOn.expect(false.B)
      d.wake.poke(1.U);d.clk.step();d.wake.poke(0.U)
      d.oscillatorOn.expect(true.B);d.gateRequest.expect(false.B)
      d.clearAck.get.poke(1.U);qualify(d)
    }
  }
  test("warm initialization discards authorization; missing source clear faults within the existing timer") {
    simulateRaw(new OscSequencer(withEpochClear=true)) {d=>
      initialize(d);qualify(d)
      d.initialize.get.poke(true.B);d.clk.step();d.initialize.get.poke(false.B)
      d.oscillatorOn.expect(true.B);d.authorized.expect(false.B);d.gateRequest.expect(false.B)
      d.clearAck.get.poke(0.U);d.clk.step(30)
      d.fault.expect(true.B);d.gateRequest.expect(false.B);d.oscillatorOn.expect(true.B)
    }
  }
  test("a missing clear acknowledgement cannot be accepted") {
    val e=intercept[Throwable] {
      simulateRaw(new OscSequencer(withEpochClear=true) {
        override protected def clearComplete(value: Bool): Bool=true.B
      }) {d=>initialize(d);qualify(d)}
    }
    assert(Iterator.iterate(e)(_.getCause).takeWhile(_!=null)
      .exists(x=>Option(x.getMessage).exists(_.contains("SOURCE_CLEAR_ACK_REQUIRED"))))
  }
}
