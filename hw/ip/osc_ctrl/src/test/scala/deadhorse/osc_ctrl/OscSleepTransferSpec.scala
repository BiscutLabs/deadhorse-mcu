package deadhorse.osc_ctrl

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Independent endpoint oracle: acknowledgement requires delivery of the
  * requested settings, including when the receiving clock is stopped. */
class OscSleepTransferSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan04/sleep-transfer-simulation").toAbsolutePath
  }
  def scenario(d: OscSleepTransfer): Unit={
    def both(n: Int): Unit=for(_<-0 until n) {d.aon.step();d.main.step(3)}
    d.requested.poke(false.B);d.modes.poke(0.U)
    d.aonReset_n.poke(false.B);d.mainReset_n.poke(false.B);both(3)
    d.applied.expect(false.B);d.appliedModes.expect(0.U)
    d.aonReset_n.poke(true.B);d.mainReset_n.poke(true.B);both(20)
    d.settled.expect(true.B)

    // Stopping main before delivery must prevent an acknowledgement.
    d.requested.poke(true.B);d.modes.poke(27.U);d.aon.step(12)
    assert(!d.settled.peek().litToBoolean,"SLEEP_ACK_BEFORE_DELIVERY")
    d.applied.expect(false.B);d.appliedModes.expect(0.U)
    both(20);d.settled.expect(true.B);d.applied.expect(true.B);d.appliedModes.expect(27.U)

    // Back-to-back settings and cancellation must converge to the latest
    // complete payload, never a mixture of independently sampled fields.
    val legal=Set((true,27),(true,42),(false,21))
    d.modes.poke(42.U);d.aon.step(2)
    d.requested.poke(false.B);d.modes.poke(21.U);d.aon.step(2)
    for(_<-0 until 30) {
      both(1)
      assert(legal((d.applied.peek().litToBoolean,d.appliedModes.peek().litValue.toInt)))
    }
    d.settled.expect(true.B);d.applied.expect(false.B);d.appliedModes.expect(21.U)

    // Either endpoint reset discards a pending transfer and clears the main
    // settings; after release the current source settings are delivered again.
    for(resetAon<-Seq(false,true)) {
      d.requested.poke(true.B);d.modes.poke(36.U);d.aon.step(2)
      if(resetAon) d.aonReset_n.poke(false.B) else d.mainReset_n.poke(false.B)
      both(3);d.applied.expect(false.B);d.appliedModes.expect(0.U)
      d.aonReset_n.poke(true.B);d.mainReset_n.poke(true.B);both(24)
      d.settled.expect(true.B);d.applied.expect(true.B);d.appliedModes.expect(36.U)
      d.requested.poke(false.B);d.modes.poke(0.U);both(24)
    }
  }
  test("sleep settings are acknowledged only after atomic main-domain delivery") {
    simulateRaw(new OscSleepTransfer)(scenario)
  }
  test("premature acknowledgement fault is rejected") {
    val failure=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new OscSleepTransfer {
        override protected def acknowledge(value: Bool): Bool=true.B
      })(scenario)
    }
    assert(failure.getMessage.contains("SLEEP_ACK_BEFORE_DELIVERY"))
  }
}
