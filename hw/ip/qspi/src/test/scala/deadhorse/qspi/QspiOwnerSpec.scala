package deadhorse.qspi
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class QspiOwnerSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t29/owner-simulation").toAbsolutePath
  }
  def exercise(d: Qspi): Unit={
    def high(b: Bool)=b.peek().litToBoolean
    d.reset_n.poke(false.B);d.dqIn.poke(0.U);d.bus.req.poke(false.B);d.bus.bits.poke(0.U.asTypeOf(d.bus.bits))
    d.clk.step(3);d.reset_n.poke(true.B)
    def access(origin: Int,addr: Int,write: Boolean=false,data: Long=0): (BigInt,Boolean)={
      d.bus.req.poke(true.B);d.bus.bits.addr.poke(addr.U);d.bus.bits.we.poke(write.B)
      d.bus.bits.wdata.poke(data.U);d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(origin.U)
      var edges=0
      while(!high(d.bus.gnt)) {d.clk.step();edges+=1;assert(edges<32)}
      d.clk.step();d.bus.req.poke(false.B)
      while(!high(d.bus.rvalid)) {d.clk.step();edges+=1;assert(edges<32)}
      val r=(d.bus.rdata.peek().litValue,high(d.bus.err))
      // Offer the next operation immediately, with no artificial idle gap.
      d.clk.step();r
    }
    for(next<-Seq(1,0,1,1,0)) {
      assert(!access(1,8,true,0xa5)._2)
      assert(!access(1,36,true,0x4f574e00L|next)._2,"QSPI_HANDOFF_RESPONSE")
      assert(access(1,28)==(BigInt(2),false),"QSPI_RESET_OWNER")
      assert(access(1,32)==(BigInt(if(next==1) 0 else 2),false),"QSPI_HANDOFF_REJECTION")
      assert(!access(1,32,true,3)._2)
      for(origin<-0 to 7) {
        val(data,err)=access(origin,8)
        assert(err==(origin!=1),"QSPI_FIXED_OWNER")
        assert(data==(if(origin==1)0xa5 else 0))
      }
    }
  }

  test("back-to-back handoff encodings cannot transfer performance ownership") {
    simulateRaw(new Qspi("build/t29/qspi/qspi_regs.json"))(exercise)
  }
  test("retaining lite access is rejected") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new Qspi("build/t29/qspi/qspi_regs.json") {
        override protected def permitted(origin: UInt,owner: UInt): Bool=origin===owner || origin===0.U
      })(exercise)
    };assert(e.getMessage.contains("QSPI_FIXED_OWNER"))
  }
}
