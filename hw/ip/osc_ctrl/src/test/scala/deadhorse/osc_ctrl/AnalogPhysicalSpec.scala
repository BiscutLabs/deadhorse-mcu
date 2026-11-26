package deadhorse.osc_ctrl

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class AnalogPhysicalSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t43/analog-physical-simulation").toAbsolutePath
  }
  def timeline(d: LfReadyPhysical): Unit={
    d.power_n.poke(false.B);d.enable.poke(false.B);d.source.step()
    var consecutive=0
    val random=new scala.util.Random(43111L)
    for(i<-0 until 200) {
      val power=i%17!=0
      val enable=i%13!=0 && (i<40 || random.nextInt(10)!=0)
      d.power_n.poke(power.B);d.enable.poke(enable.B)
      if(!power || !enable) {
        consecutive=0
        assert(!d.ready.peek().litToBoolean,"LF_ASSERTION_NOT_IMMEDIATE")
      }
      d.source.step()
      consecutive=if(power && enable) consecutive+1 else 0
      assert(d.ready.peek().litToBoolean==(consecutive>=4),"LF_FOUR_EDGE_CONTRACT")
    }
  }
  test("physical readiness requires four fresh edges after power or disable") {
    simulateRaw(new LfReadyPhysical)(timeline)
  }
  test("one-edge-early readiness is rejected") {
    val failure=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new LfReadyPhysical {
        override protected def qualifiedReady(third: Bool,fourth: Bool): Bool=third
      })(timeline)
    }
    assert(failure.getMessage.contains("LF_FOUR_EDGE_CONTRACT"))
  }
}
