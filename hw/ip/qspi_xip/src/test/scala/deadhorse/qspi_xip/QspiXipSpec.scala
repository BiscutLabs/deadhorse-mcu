package deadhorse.qspi_xip
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import deadhorse.lib.LocalBus
import deadhorse.qspi.Qspi
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class QspiXipSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t30/xip-simulation").toAbsolutePath
  }
  test("native endian/range permissions, captured logging command, configuration barrier and quad reads") {
    simulateRaw(new Qspi("build/t30/qspi/qspi_regs.json",withXip=true)) {d=>
      def byte(a: Long)=((a*37)^(a>>>7)^0xa3).toInt&255
      val peer=new FlashPeer(d.cs_n,d.sclk,d.dqOut,d.dqEnable,d.dqIn,d.reset_n,byte,
        Map(3->(3,false,false,0),19->(4,false,false,0),235->(4,true,true,6)))
      var cycle=0
      def tick(n: Int=1): Unit=for(_<-0 until n) {peer.observe();d.clk.step();cycle+=1}
      def high(v: Bool)=v.peek().litToBoolean
      val x=d.xip.get
      d.reset_n.poke(false.B);d.dqIn.poke(0.U)
      for(b<-Seq(d.bus,x)) {b.req.poke(false.B);b.bits.poke(0.U.asTypeOf(b.bits))}
      tick(3);d.reset_n.poke(true.B);tick(4)
      def drive(b: LocalBus,a: Long,w: Boolean,v: Long,origin: Int): Unit={
        b.req.poke(true.B);b.bits.addr.poke(a.U);b.bits.we.poke(w.B);b.bits.wdata.poke(v.U)
        b.bits.be.poke(15.U);b.bits.origin.poke(origin.U)
      }
      def access(b: LocalBus,a: Long,w: Boolean=false,v: Long=0,origin: Int=0): (BigInt,Boolean)={
        val begin=cycle;drive(b,a,w,v,origin)
        while(!high(b.gnt)) {tick();assert(cycle-begin<106630,"XIP_GRANT_BOUND")}
        tick();b.req.poke(false.B)
        while(!high(b.rvalid)) {tick();assert(cycle-begin<106630,"XIP_RESPONSE_BOUND")}
        val result=(b.rdata.peek().litValue,high(b.err));tick(3);result
      }
      def wr(a: Int,v: Long,owner: Int=0): Unit=assert(!access(d.bus,a,true,v,owner)._2)
      def rd(a: Int,owner: Int=0): BigInt={val(v,e)=access(d.bus,a,origin=owner);assert(!e);v}
      def read(a: Long): Unit={
        val(v,e)=access(x,0x10000000L+a,origin=1)
        val expected=(0 until 4).foldLeft(0L)((r,i)=>r|(byte(a+i).toLong<<(8*i)))
        assert(!e && v==expected,"XIP_NATIVE_ENDIAN")
      }
      assert(access(x,0x10000000L,origin=1)._2)
      wr(0x100,0x307);wr(0x108,0x58495021L);assert(rd(0x10c)==1)
      for(a<-Seq(0L,4L,0x1234L,0xfffffcL)) read(a)
      for(a<-Seq(0x11000000L,0x20000000L,0x0ffffffcL,0x10000001L)) assert(access(x,a,origin=1)._2)
      for(o<-Seq(0,2,3,4,5,6,7)) assert(access(x,0x10000000L,origin=o)._2)
      assert(access(x,0x10000000L,true,0,1)._2)
      wr(20,0x51535049L);assert((rd(32)&2)!=0,"XIP_BOOT_FLASH_MUTATION");wr(32,3)
      // Queue a bounded CS1 command while the native read owns the engine.
      wr(0,1);wr(8,6)
      drive(x,0x10000100L,false,0,1)
      while(!high(x.gnt)) tick();tick();x.req.poke(false.B)
      wr(20,0x51535049L);wr(20,0x51535049L)
      wr(0x100,0x1309);wr(0x108,0x58495021L);wr(36,0x4f574e01L)
      assert((rd(32)&2)!=0,"XIP_BUSY_BARRIER")
      val waitFrom=cycle
      while(!high(x.rvalid)) {tick();assert(cycle-waitFrom<106630)}
      assert(!high(x.err));tick(3)
      while((rd(28)&1)!=0) {tick();assert(cycle-waitFrom<106630)}
      assert(peer.frames.takeRight(2).map(_._1).toSeq==Seq(0,1),"XIP_LOGGING_ARBITRATION")
      assert(rd(24)==0);wr(32,3)
      // MMIO handoff cannot remove the independent native read permission.
      wr(36,0x4f574e01L);read(0x20)
      wr(0x108,0x58495021L,1);read(0x1000020L)
      wr(0x100,0xeb39,1);wr(0x104,4|(6<<8),1);wr(0x108,0x58495021L,1)
      read(0x1234560L)
      wr(0x100,0xeb38,1);wr(0x108,0x58495021L,1)
      assert(access(x,0x10000000L,origin=1)._2)
      wr(0x100,0x307,1);wr(0x104,4,1);wr(0x108,0x58495021L,1)
      drive(x,0x10000000L,false,0,1)
      while(!high(x.gnt))tick();tick();x.req.poke(false.B)
      while(d.cs_n.peek().litValue==3)tick()
      d.reset_n.poke(false.B)
      assert(d.csEnable.peek().litValue==0 && d.dqEnable.peek().litValue==0 && !high(x.rvalid),"XIP_SERVICE_RESET")
      tick(3);d.reset_n.poke(true.B);tick(8)
      assert(access(x,0x10000000L,origin=1)._2,"XIP_RESET_DISABLED")
    }
  }
}
