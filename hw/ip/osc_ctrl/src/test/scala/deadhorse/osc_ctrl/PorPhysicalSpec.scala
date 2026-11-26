package deadhorse.osc_ctrl

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class PorPhysicalSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t43/por-physical-simulation").toAbsolutePath
  }
  def exercise(d: PorQualifierPhysical, edges: Int): Unit={
    d.cold_n.poke(false.B);d.rawGood.poke(false.B);d.threshold.poke(0.U)
    d.reference.step(2)
    assert(!d.supplyReset_n.peek().litToBoolean)
    assert(!d.powerOn_n.peek().litToBoolean && !d.brownout.peek().litToBoolean)
    d.cold_n.poke(true.B);d.rawGood.poke(true.B)
    // Two selector samples, two safe-release samples, then the requested
    // consecutive good samples. This is the physical controller's latency.
    for(i<-1 to edges+4) {
      d.reference.step()
      assert(d.supplyReset_n.peek().litToBoolean==(i==edges+4),"POR_PHYSICAL_RELEASE_COUNT")
    }
    assert(!d.powerOn_n.peek().litToBoolean)
    d.reference.step();assert(d.powerOn_n.peek().litToBoolean)
    // Every binary encoding; only 01 selects the higher analog threshold.
    // A safe already-released rail stays released while selection settles.
    for(code<-Seq(1,2,3,0)) {
      d.threshold.poke(code.U)
      assert(d.higher.peek().litToBoolean==(code==1))
      assert(d.supplyReset_n.peek().litToBoolean)
      d.reference.step(5)
      assert(d.supplyReset_n.peek().litToBoolean)
    }
    // A raw fault without a reference edge must cancel release immediately.
    d.rawGood.poke(false.B)
    assert(!d.supplyReset_n.peek().litToBoolean)
    assert(d.powerOn_n.peek().litToBoolean)
    d.rawGood.poke(true.B)
    d.reference.step()
    assert(d.brownout.peek().litToBoolean)
    // Walk to the last qualification edge, then change the threshold.
    d.reference.step(edges)
    assert(!d.supplyReset_n.peek().litToBoolean)
    d.threshold.poke(1.U)
    for(i<-1 to edges+4) {
      d.reference.step()
      assert(d.supplyReset_n.peek().litToBoolean==(i==edges+4),"POR_SELECTION_RESTART")
    }
    assert(d.brownout.peek().litToBoolean)
    // During incomplete qualification, a selector excursion between local
    // edges must discard the history even if it returns to the old code.
    d.rawGood.poke(false.B);assert(!d.supplyReset_n.peek().litToBoolean)
    d.rawGood.poke(true.B);d.reference.step(edges+1)
    d.threshold.poke(0.U);assert(!d.supplyReset_n.peek().litToBoolean)
    d.threshold.poke(1.U)
    for(i<-1 to edges+2) {
      d.reference.step()
      assert(d.supplyReset_n.peek().litToBoolean==(i==edges+2),"POR_SUBCYCLE_SELECTION_RESTART")
    }
    d.cold_n.poke(false.B)
    assert(!d.supplyReset_n.peek().litToBoolean)
    assert(!d.powerOn_n.peek().litToBoolean && !d.brownout.peek().litToBoolean)
  }
  for(edges<-Seq(8,1000)) {
    test(s"physical POR qualifies $edges samples and preserves the power epoch") {
      simulateRaw(new PorQualifierPhysical(edges))(d=>exercise(d,edges))
    }
  }
  test("one-sample-early physical release is rejected") {
    val failure=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new PorQualifierPhysical(8) {
        override protected def complete(count: UInt): Bool=count===6.U
      })(d=>exercise(d,8))
    }
    assert(failure.getMessage.contains("POR_PHYSICAL_RELEASE_COUNT"))
  }
}
