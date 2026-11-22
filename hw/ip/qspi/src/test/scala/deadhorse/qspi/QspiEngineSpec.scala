package deadhorse.qspi
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class QspiEngineSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t29/engine-simulation").toAbsolutePath
  }
  def exercise(d: QspiEngine): Unit={
    def high(b: Bool)=b.peek().litToBoolean
    d.reset_n.poke(false.B);d.start.poke(false.B);d.command.poke(0.U.asTypeOf(d.command));d.dq.poke(0.U)
    d.clk.step(3);d.reset_n.poke(true.B)
    for((half,ab,db,dummy,quad)<-Seq((4,0,0,0,false),(7,3,4,8,true),(255,4,4,31,false))) {
      d.command.halfPeriod.poke(half.U);d.command.addressBytes.poke(ab.U);d.command.dataBytes.poke(db.U)
      d.command.dummy.poke(dummy.U);d.command.quadAddress.poke(quad.B);d.command.quadData.poke(quad.B)
      d.command.read.poke(true.B);d.start.poke(true.B);d.clk.step();d.start.poke(false.B)
      assert(high(d.busy) && !high(d.done) && d.cs_n.peek().litValue==2)
      val clocks=8+(ab+db)*(if(quad)2 else 8)+dummy
      val expectedCsHigh=(2*clocks+1)*half
      val expectedDone=(2*clocks+2)*half
      for(edge<-1 to expectedDone) {
        d.clk.step()
        assert((d.cs_n.peek().litValue==3)==(edge>=expectedCsHigh),"QSPI_CS_INTERVAL")
        assert(high(d.busy)==(edge<expectedDone) && high(d.done)==(edge==expectedDone),"QSPI_BUSY_GAP")
        assert(edge<=53299)
      }
      d.clk.step();assert(!high(d.done) && !high(d.busy))
      println(s"MEASURED QSPI H=$half address=$ab data=$db dummy=$dummy quad=$quad: CS high at $expectedCsHigh, done at $expectedDone main edges after accepted start")
    }
  }
  test("busy and done include the exact CS-high gap at divider extremes") {
    simulateRaw(new QspiEngine)(exercise)
  }
  test("shortening the physical gap is rejected by the same timing oracle") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new QspiEngine {override protected def gapReload(half: UInt): UInt=0.U})(exercise)
    };assert(e.getMessage.contains("QSPI_BUSY_GAP"))
  }
}
