package deadhorse.usb

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class UsbRegistersSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t19/register-simulation").toAbsolutePath
  }
  test("owner, byte masks, non-consuming reads, commands and set-dominant events") {
    simulateRaw(new UsbRegisters("build/t19/regmap/usb_regs.json")) { d=>
      def high(b: Bool)=b.peek().litValue==1
      var pushes=Vector.empty[Int];var pops=0;var acknowledgements=0
      def step(n: Int=1): Unit=for(_<-0 until n) {
        if(high(d.txPush)) pushes :+= d.txData.peek().litValue.toInt
        if(high(d.rxPop)) pops+=1
        if(high(d.wakeAck)) acknowledgements+=1
        d.clk.step()
      }
      d.reset_n.poke(false.B);d.owner.poke(3.U);d.bus.req.poke(false.B)
      d.bus.bits.addr.poke(0.U);d.bus.bits.wdata.poke(0.U);d.bus.bits.we.poke(false.B)
      d.bus.bits.be.poke(0.U);d.bus.bits.origin.poke(0.U)
      d.txReady.poke(false.B);d.rxValid.poke(false.B);d.rxData.poke(0x96.U)
      d.configured.poke(false.B);d.connected.poke(false.B);d.frame.poke(0.U)
      d.sessionReset.poke(false.B);d.resume.poke(false.B)
      step(3);d.reset_n.poke(true.B);step(4)
      def access(offset: Int,write: Boolean=false,value: Int=0,mask: Int=15,origin: Int=3):(BigInt,Boolean)={
        d.bus.req.poke(true.B);d.bus.bits.addr.poke((BigInt("40040800",16)+offset).U)
        d.bus.bits.we.poke(write.B);d.bus.bits.wdata.poke(value.U);d.bus.bits.be.poke(mask.U);d.bus.bits.origin.poke(origin.U)
        var granted=false;var done=false;var result=BigInt(0);var error=false
        for(_<-0 until 32 if !done) {
          val take=high(d.bus.req)&&high(d.bus.gnt)
          if(high(d.bus.rvalid)) {assert(granted);result=d.bus.rdata.peek().litValue;error=high(d.bus.err);done=true}
          step();if(take){assert(!granted);granted=true;d.bus.req.poke(false.B)}
        }
        assert(done,"USB bus response deadline");step(4)
        if(write||error) assert(result==0)
        (result,error)
      }
      def read(offset: Int): BigInt={val(v,e)=access(offset);assert(!e);v}
      def write(offset: Int,value: Int,mask: Int=15): Unit=assert(!access(offset,true,value,mask)._2)
      assert(read(0)==0 && read(0x14)==0 && !high(d.irq))
      for(origin<-0 until 8 if origin!=3;offset<-Seq(0,4,8,0x14,0x18))
        assert(access(offset,true,255,15,origin)._2)
      assert(pushes.isEmpty && pops==0 && acknowledgements==0 && !high(d.enabled))
      for(offset<-Seq(1,2,3,0x20,0xfc,0x100)) assert(access(offset,true,1)._2)
      for(mask<-0 until 16) {
        val old=pushes.length;write(4,0xa0+mask,mask)
        assert(pushes.length-old==(mask&1))
        if((mask&1)!=0) assert(pushes.last==0xa0+mask)
      }
      assert(read(0x14)==1);write(0x18,2);assert(high(d.irq))
      write(0x14,1,0);assert(read(0x14)==1);write(0x14,1);assert(!high(d.irq))
      write(8,3);assert(pops==1 && acknowledgements==1 && read(0x14)==2)
      d.rxValid.poke(true.B);d.configured.poke(true.B);d.connected.poke(true.B)
      d.txReady.poke(true.B);d.frame.poke(0x567.U);step(4)
      assert(read(0x10)==15 && read(0x1c)==0x567)
      assert(read(0xc)==0x96 && read(0xc)==0x96 && pops==1)
      write(0xc,0x11);assert(read(0xc)==0x96)
      d.sessionReset.poke(true.B);d.resume.poke(true.B);step(4)
      write(0x14,15);assert(read(0x14)==12,"hardware event must win W1C")
      d.sessionReset.poke(false.B);d.resume.poke(false.B);write(0x14,15)
      assert(read(0x14)==0 && !high(d.irq))
      write(0x18,1);assert(high(d.irq));d.rxValid.poke(false.B);step(3);assert(!high(d.irq))
      write(0,1);assert(high(d.enabled));write(0,0,0);assert(high(d.enabled))
      d.reset_n.poke(false.B);step(2);assert(!high(d.enabled) && !high(d.irq))
    }
  }
}
