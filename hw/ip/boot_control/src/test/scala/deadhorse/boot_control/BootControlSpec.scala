package deadhorse.boot_control
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class BootControlSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t28/mmio-simulation").toAbsolutePath
  }
  def exercise(d: BootControl): Unit={
    def high(v: Bool)=v.peek().litToBoolean
    d.epochReset_n.poke(false.B);d.reset_n.poke(false.B);d.startAccepted.poke(false.B)
    d.bus.req.poke(false.B);d.bus.bits.poke(0.U.asTypeOf(d.bus.bits));d.clk.step(3)
    d.epochReset_n.poke(true.B);d.reset_n.poke(true.B)
    def access(a: Int,w: Boolean=false,v: Long=0,be: Int=15,origin: Int=0): (BigInt,Boolean)={
      d.bus.req.poke(true.B);d.bus.bits.addr.poke(a.U);d.bus.bits.we.poke(w.B)
      d.bus.bits.wdata.poke(v.U);d.bus.bits.be.poke(be.U);d.bus.bits.origin.poke(origin.U)
      var n=0
      while(!high(d.bus.gnt)) {d.clk.step();n+=1;assert(n<32)}
      d.clk.step();d.bus.req.poke(false.B)
      while(!high(d.bus.rvalid)) {d.clk.step();n+=1;assert(n<32)}
      val r=(d.bus.rdata.peek().litValue,high(d.bus.err));d.clk.step(3);r
    }
    def wr(a: Int,v: Long): Unit=assert(!access(a,true,v)._2)
    def rd(a: Int): BigInt={val(v,e)=access(a);assert(!e);v}
    val key=0x50455246L
    assert(rd(0)==0 && rd(4)==0)
    wr(4,key);assert(!high(d.released) && rd(8)==1,"BOOT_EARLY");wr(8,1)
    d.startAccepted.poke(true.B);d.clk.step();d.startAccepted.poke(false.B)
    assert(rd(0)==1)
    for(o<-1 to 7) assert(access(4,true,key,origin=o)._2,"BOOT_OWNER")
    assert(!high(d.released),"BOOT_OWNER")
    for(be<-1 to 14) assert(access(4,true,key,be=be)._2,"BOOT_PARTIAL")
    assert(!access(4,true,key,be=0)._2 && !high(d.released))
    for(a<-Seq(1,12,256)) assert(access(a,true,key)._2)
    wr(4,0);assert(!high(d.released) && rd(8)==1,"BOOT_KEY");wr(8,1)
    // Interrupt before acceptance, after adapter acceptance, and after the
    // register command pulse is generated but before the state consumes it.
    for(edges<-0 to 2) {
      d.bus.req.poke(true.B);d.bus.bits.addr.poke(4.U);d.bus.bits.we.poke(true.B)
      d.bus.bits.wdata.poke(key.U);d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(0.U)
      var n=0
      while(!high(d.bus.gnt)) {d.clk.step();n+=1;assert(n<32)}
      if(edges>0) {d.clk.step();d.bus.req.poke(false.B)}
      if(edges>1) d.clk.step()
      assert(!high(d.released),"BOOT_CANCEL_PRECONDITION")
      d.reset_n.poke(false.B);d.clk.step();d.bus.req.poke(false.B)
      d.reset_n.poke(true.B)
      for(_<-0 until 8) {
        d.clk.step();assert(!high(d.released) && !high(d.bus.rvalid) && !high(d.bus.err),"BOOT_CANCEL_REPLAY")
      }
      assert(rd(0)==1 && rd(8)==0,"BOOT_CANCEL")
    }
    wr(4,key);assert(high(d.released) && rd(0)==3,"BOOT_RELEASE")
    wr(4,key);assert(rd(8)==0,"BOOT_IDEMPOTENT")
    wr(4,0);assert(high(d.released) && rd(8)==1)
    d.reset_n.poke(false.B);d.clk.step(2);d.reset_n.poke(true.B);d.clk.step(4)
    assert(high(d.released) && rd(0)==3 && rd(8)==0,"BOOT_SERVICE_RETENTION")
    d.epochReset_n.poke(false.B);d.clk.step();assert(!high(d.released))
    d.epochReset_n.poke(true.B);d.clk.step(4);assert(rd(0)==0)
  }
  test("lite-owned release, keys, byte lanes, canceled transport and retained epoch") {
    simulateRaw(new BootControl("build/t28/boot_control/boot_control_regs.json"))(exercise)
  }
  test("owner bypass is rejected by the same transaction oracle") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new BootControl("build/t28/boot_control/boot_control_regs.json") {
        override protected def permitted(origin: UInt): Bool=true.B
      })(exercise)
    };assert(e.getMessage.contains("BOOT_OWNER"))
  }
}
