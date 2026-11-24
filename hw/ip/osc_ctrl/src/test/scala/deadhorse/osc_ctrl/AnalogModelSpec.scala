package deadhorse.osc_ctrl

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class AnalogModelSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan04/analog-simulation").toAbsolutePath
  }
  test("approved threshold changes never bypass assertion or release qualification") {
    simulateRaw(new PorBrownoutModel(8)) {d=>
      d.supplyMv.poke(0.U);d.threshold.poke(0.U);d.reference.step(2)
      d.supplyMv.poke(3400.U);d.reference.step(9);d.supplyReset_n.expect(true.B)
      // A still-valid supply can remain released across either selector edge.
      for(select<-Seq(1,0,1)) {d.threshold.poke(select.U);d.supplyReset_n.expect(true.B);d.reference.step()}
      d.threshold.poke(0.U);d.supplyMv.poke(3150.U);d.reference.step(2)
      d.supplyReset_n.expect(true.B)
      // Raising the threshold at this supply asserts immediately, without a clock.
      d.threshold.poke(1.U);d.supplyReset_n.expect(false.B);d.reference.step()
      d.supplyMv.poke(3299.U);d.reference.step(12);d.supplyReset_n.expect(false.B)
      d.supplyMv.poke(3300.U);d.reference.step(7);d.supplyReset_n.expect(false.B)
      d.reference.step();d.supplyReset_n.expect(true.B)
      // Lowering the selection during asserted reset still needs a full release.
      d.supplyMv.poke(3199.U);d.supplyReset_n.expect(false.B);d.reference.step()
      d.threshold.poke(0.U);d.supplyReset_n.expect(false.B)
      d.supplyMv.poke(3200.U);d.reference.step(7);d.supplyReset_n.expect(false.B)
      d.reference.step();d.supplyReset_n.expect(true.B)
    }
  }
  def freshThresholdQualification(d: PorBrownoutModel): Unit={
      d.supplyMv.poke(0.U);d.threshold.poke(0.U);d.reference.step(2)
      d.supplyMv.poke(3250.U);d.reference.step(6);d.supplyReset_n.expect(false.B)
      d.threshold.poke(1.U);d.supplyMv.poke(3400.U)
      d.reference.step(7)
      assert(!d.supplyReset_n.peek().litToBoolean,"POR_OLD_THRESHOLD_SAMPLES_REUSED")
      d.reference.step();d.supplyReset_n.expect(true.B)
  }
  test("threshold change restarts an incomplete release qualification") {
    simulateRaw(new PorBrownoutModel(8))(freshThresholdQualification)
  }
  test("old-threshold qualification reuse fault is detected") {
    val failure=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new PorBrownoutModel(8) {
        override protected def thresholdChanged(value: Bool): Bool=false.B
      })(freshThresholdQualification)
    }
    assert(failure.getMessage.contains("POR_OLD_THRESHOLD_SAMPLES_REUSED"))
  }
  def thresholdAssertion(d: PorBrownoutModel): Unit={
    d.supplyMv.poke(0.U);d.threshold.poke(0.U);d.reference.step(2)
    d.supplyMv.poke(3400.U);d.reference.step(9);d.supplyReset_n.expect(true.B)
    d.supplyMv.poke(3150.U);d.threshold.poke(1.U)
    assert(!d.supplyReset_n.peek().litToBoolean,"POR_THRESHOLD_ASSERTION_LOST")
  }
  test("ignored threshold fault fails the actual supply/reset oracle") {
    val failure=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new PorBrownoutModel(8) {
        override protected def selectedThreshold(value: UInt): UInt=0.U
      })(thresholdAssertion)
    }
    assert(failure.getMessage.contains("POR_THRESHOLD_ASSERTION_LOST"))
  }
  test("POR model fast and slow ramps, qualified release, hysteresis and brownout") {
    simulateRaw(new PorBrownoutModel(8)) {d=>
      def powerOff(): Unit={
        d.supplyMv.poke(0.U);d.threshold.poke(0.U);d.reference.step(2)
        d.supplyReset_n.expect(false.B);d.powerOn_n.expect(false.B);d.brownout.expect(false.B)
      }
      for(slow<-Seq(false,true)) {
        powerOff()
        if(slow) for(mv<-100 to 3190 by 10) {
          d.supplyMv.poke(mv.U);d.reference.step();d.supplyReset_n.expect(false.B)
        }
        d.supplyMv.poke(3300.U)
        d.reference.step(7);d.supplyReset_n.expect(false.B)
        d.reference.step();d.supplyReset_n.expect(true.B)
        d.reference.step();d.powerOn_n.expect(true.B)
        d.supplyMv.poke(3150.U);d.reference.step(3);d.supplyReset_n.expect(true.B)
        d.brownout.expect(false.B)
        d.supplyMv.poke(3099.U);d.supplyReset_n.expect(false.B)
        d.reference.step();d.brownout.expect(true.B);d.powerOn_n.expect(true.B)
        d.supplyMv.poke(3150.U);d.reference.step(10);d.supplyReset_n.expect(false.B)
        d.supplyMv.poke(3200.U);d.reference.step(7);d.supplyReset_n.expect(false.B)
        d.reference.step();d.supplyReset_n.expect(true.B);d.brownout.expect(true.B)
      }
    }
  }
}
