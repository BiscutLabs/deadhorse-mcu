package deadhorse.osc_ctrl

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Directed event/deadline oracle. The source model acknowledges requests only
  * when the test has supplied the specified clocks, independently of the FSM. */
class OscSequencerSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan04/sequencer-simulation").toAbsolutePath
  }
  def initialize(d: OscSequencer): Unit={
    d.reset_n.poke(false.B);d.sleep.poke(false.B);d.deep.poke(false.B);d.forceRun.poke(false.B)
    d.mainHold.poke(false.B);d.oscillatorHold.poke(false.B);d.coreIdle.poke(true.B)
    d.gateClosed.poke(false.B);d.stable.poke(false.B)
    d.wake.poke(0.U);d.wakeEnable.poke(255.U)
    d.delayTicks.poke(3.U);d.timeoutTicks.poke(9.U);d.stableEdges.poke(5.U)
    d.clk.step(2);d.oscillatorOn.expect(true.B);d.gateRequest.expect(false.B)
    d.reset_n.poke(true.B)
  }
  def boot(d: OscSequencer): Unit={
    initialize(d)
    for(_<-0 until 3) {d.clk.step();d.gateRequest.expect(false.B)}
    d.clk.step(2);d.qualify.expect(true.B);d.count.expect(5.U)
    d.stable.poke(true.B);d.clk.step();d.gateRequest.expect(true.B)
  }
  test("startup captures settings, waits for a fresh stable report, and times out safely") {
    simulateRaw(new OscSequencer) {d=>
      initialize(d)
      d.clk.step();d.delayTicks.poke(1.U);d.stableEdges.poke(1.U)
      d.clk.step(2);d.qualify.expect(false.B);d.count.expect(5.U)
      d.clk.step();d.qualify.expect(true.B)
      d.clk.step(8);d.fault.expect(false.B);d.gateRequest.expect(false.B)
      d.clk.step();d.fault.expect(true.B);d.oscillatorOn.expect(true.B)
      d.stable.poke(true.B);d.clk.step(4);d.gateRequest.expect(false.B)
    }
  }
  test("stop requires WFI, drained holds and source acknowledgement; USB retains OSC_EN") {
    simulateRaw(new OscSequencer) {d=>
      boot(d);d.deep.poke(true.B);d.sleep.poke(true.B);d.coreIdle.poke(false.B)
      d.clk.step();d.sleep.poke(false.B);d.clk.step(3)
      d.gateRequest.expect(true.B);d.oscillatorOn.expect(true.B)
      d.coreIdle.poke(true.B);d.mainHold.poke(true.B);d.clk.step(3)
      d.gateRequest.expect(true.B);d.oscillatorOn.expect(true.B)
      d.mainHold.poke(false.B);d.clk.step();d.gateRequest.expect(false.B)
      d.clk.step(4);d.oscillatorOn.expect(true.B)
      d.oscillatorHold.poke(true.B);d.gateClosed.poke(true.B);d.clk.step()
      d.state.expect(2.U);d.oscillatorOn.expect(true.B)
      d.wake.poke(32.U);d.clk.step();d.wake.poke(0.U);d.clk.step()
      d.gateRequest.expect(true.B);d.lastWake.expect(32.U)
    }
  }
  def resetWake(d: OscSequencer,phase: String): Unit={
    boot(d);d.wakeEnable.poke(0.U)
    if(phase!="RUN") {
      d.deep.poke((phase=="DEEP" || phase=="STARTING").B)
      d.sleep.poke(true.B);d.clk.step();d.sleep.poke(false.B)
      if(phase!="STOPPING") {
        d.clk.step(2);d.gateClosed.poke(true.B);d.clk.step()
        d.state.expect(2.U)
        if(phase=="STARTING") {
          d.stable.poke(false.B);d.mainHold.poke(true.B);d.clk.step()
          d.mainHold.poke(false.B);d.state.expect(3.U)
        }
      }
    }
    d.forceRun.poke(true.B);d.sleep.poke(true.B);d.clk.step()
    assert(d.oscillatorOn.peek().litToBoolean,"OSC_RESET_WAKE_LOST")
    if(phase=="DEEP" || phase=="STARTING") {
      d.gateRequest.expect(false.B);d.stable.poke(false.B);d.gateClosed.poke(false.B)
      d.clk.step(5);d.qualify.expect(true.B);d.gateRequest.expect(false.B)
      d.stable.poke(true.B);d.clk.step(2)
    }
    assert(d.state.peek().litValue==0 && d.gateRequest.peek().litToBoolean,"OSC_RESET_SLEEP_NOT_CANCELLED")
    d.clk.step(3);d.state.expect(0.U) // forceRun beats repeated sleep requests.
    d.sleep.poke(false.B);d.forceRun.poke(false.B);d.clk.step(2);d.state.expect(0.U)
  }
  for(phase<-Seq("RUN","STOPPING","LIGHT","DEEP","STARTING"))
  test(s"unmaskable service-reset demand cancels sleep in $phase") {
    simulateRaw(new OscSequencer)(d=>resetWake(d,phase))
  }
  test("ignored reset-demand fault is rejected by the same OFF oracle") {
    val failure=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new OscSequencer {
        override protected def forcedRun(value: Bool): Bool=false.B
      })(d=>resetWake(d,"DEEP"))
    }
    assert(failure.getMessage.contains("OSC_RESET_WAKE_LOST"))
  }
  def wakeExercise(d: OscSequencer): Unit={
    boot(d)
    for(bit<-0 until 8) {
      d.deep.poke(true.B);d.sleep.poke(true.B);d.clk.step();d.sleep.poke(false.B)
      d.clk.step(2);d.gateClosed.poke(true.B);d.clk.step()
      d.oscillatorOn.expect(false.B);d.gateRequest.expect(false.B)
      d.stable.poke(false.B);d.gateClosed.poke(false.B)
      d.wake.poke((1<<bit).U);d.clk.step();d.wake.poke(0.U)
      d.oscillatorOn.expect(true.B);d.clk.step(4);d.qualify.expect(true.B)
      d.stable.poke(true.B);d.clk.step(2)
      d.gateRequest.expect(true.B)
      assert(d.lastWake.peek().litValue==(1<<bit),"OSC_WAKE_CAPTURE")
    }
  }
  test("every one-edge wake survives oscillator-off startup") {
    simulateRaw(new OscSequencer)(wakeExercise)
  }
  test("lost-wake fault is detected by the same scenario") {
    val failed=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new OscSequencer {
        override protected def capturedWake(value: UInt): UInt=0.U
      })(wakeExercise)
    }
    assert(failed.getMessage.contains("OSC_WAKE_CAPTURE"))
  }
  test("wake in STOPPING or simultaneous with sleep cancels shutdown") {
    simulateRaw(new OscSequencer) {d=>
      boot(d);d.sleep.poke(true.B);d.wake.poke(1.U);d.clk.step()
      d.state.expect(0.U);d.sleep.poke(false.B);d.wake.poke(0.U);d.clk.step()
      d.sleep.poke(true.B);d.clk.step();d.sleep.poke(false.B)
      d.wake.poke(128.U);d.clk.step();d.wake.poke(0.U);d.clk.step()
      d.gateRequest.expect(true.B);d.lastWake.expect(128.U);d.oscillatorOn.expect(true.B)
    }
  }
}
