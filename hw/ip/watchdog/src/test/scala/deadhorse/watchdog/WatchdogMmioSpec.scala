package deadhorse.watchdog
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class WatchdogMmioSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t26/mmio-simulation").toAbsolutePath
  }
  def exercise(d: Watchdog): Unit={
    d.por_n.poke(false.B);d.reset_n.poke(false.B);d.bus.req.poke(false.B)
    d.bus.bits.poke(0.U.asTypeOf(d.bus.bits));d.clk.step(3);d.por_n.poke(true.B);d.reset_n.poke(true.B)
    def access(a: Int,w: Boolean=false,v: Long=0,be: Int=15,origin: Int=1): (BigInt,Boolean)={
      d.bus.req.poke(true.B);d.bus.bits.addr.poke(a.U);d.bus.bits.we.poke(w.B)
      d.bus.bits.wdata.poke(v.U);d.bus.bits.be.poke(be.U);d.bus.bits.origin.poke(origin.U)
      var n=0
      while(!d.bus.gnt.peek().litToBoolean) {d.clk.step();n+=1;assert(n<32)}
      d.clk.step();d.bus.req.poke(false.B)
      while(!d.bus.rvalid.peek().litToBoolean) {d.clk.step();n+=1;assert(n<32)}
      val result=(d.bus.rdata.peek().litValue,d.bus.err.peek().litToBoolean);d.clk.step(2);result
    }
    def wr(a: Int,v: Long): Unit=assert(!access(a,true,v)._2)
    def rd(a: Int): BigInt={val(v,e)=access(a);assert(!e);v}
    assert(access(0,true,999,origin=0)._2,"WATCHDOG_OWNER")
    for(a<-Seq(1,0x24,0x100)) assert(access(a,true,999)._2)
    wr(0,1000);wr(4,2);wr(8,20)
    assert(access(12,true,0x57445354L,be=3)._2);assert(!d.active.peek().litToBoolean)
    wr(12,0x1234);assert(rd(32)==1);wr(32,1);assert(rd(32)==0)
    wr(12,0x57445354L);assert(d.active.peek().litToBoolean)
    wr(0,0xffffffffL);wr(12,0x57445354L);assert(rd(32)==1)
    val left=rd(24);assert(left<1000,"WATCHDOG_IMMUTABLE")
    wr(16,0x57444644L);assert(rd(24)>left)
    d.clk.step(1000);assert(d.cause.peek().litToBoolean && d.crashes.peek().litValue==1)
    d.reset_n.poke(false.B);d.clk.step(2);d.reset_n.poke(true.B);d.clk.step(2)
    assert(rd(28)==1 && rd(20)==8 && rd(0)==0,"WATCHDOG_EPOCH_RETENTION")
    d.por_n.poke(false.B);d.reset_n.poke(false.B);d.clk.step()
    assert(d.crashes.peek().litValue==0 && !d.cause.peek().litToBoolean)
  }
  test("generated map ownership, keys, byte lanes, immutable active setting and reset retention") {
    simulateRaw(new Watchdog("build/t26/watchdog/watchdog_regs.json"))(exercise)
  }
  test("actual owner bypass is caught") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new Watchdog("build/t26/watchdog/watchdog_regs.json") {
        override protected def permitted(origin: UInt): Bool=true.B
      })(exercise)
    };assert(e.getMessage.contains("WATCHDOG_OWNER"))
  }
}
