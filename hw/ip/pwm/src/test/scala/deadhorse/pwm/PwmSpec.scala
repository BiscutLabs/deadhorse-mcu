package deadhorse.pwm
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class PwmSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t22/peripheral-simulation").toAbsolutePath
  }
  val json="build/t22/pwm/pwm_regs.json"
  def high(v: Bool): Boolean=v.peek().litToBoolean
  def init(d: Pwm): Unit={
    d.reset_n.poke(false.B);d.owner.poke(1.U);d.dmaAck.poke(0.U)
    d.bus.req.poke(false.B);d.bus.bits.poke(0.U.asTypeOf(d.bus.bits));d.clk.step(3)
    d.reset_n.poke(true.B);d.clk.step(3)
  }
  def access(d: Pwm,a: Int,w: Boolean=false,v: Int=0,be: Int=15,origin: Int=1): (BigInt,Boolean)={
    d.bus.req.poke(true.B);d.bus.bits.addr.poke(a.U);d.bus.bits.we.poke(w.B)
    d.bus.bits.wdata.poke(v.U);d.bus.bits.be.poke(be.U);d.bus.bits.origin.poke(origin.U)
    var n=0
    while(!high(d.bus.gnt)) {d.clk.step();n+=1;assert(n<64,"PWM_GRANT")}
    d.clk.step();d.bus.req.poke(false.B)
    while(!high(d.bus.rvalid)) {d.clk.step();n+=1;assert(n<64,"PWM_RESPONSE")}
    val result=(d.bus.rdata.peek().litValue,high(d.bus.err));d.clk.step(2)
    assert(!high(d.bus.rvalid),"PWM_DUPLICATE_REPLY");result
  }
  def wr(d: Pwm,a: Int,v: Int,be: Int=15): Unit=assert(!access(d,a,true,v,be)._2)
  def rd(d: Pwm,a: Int): BigInt={val(v,e)=access(d,a);assert(!e);v}
  def samples(d: Pwm,n: Int): Seq[BigInt]=(0 until n).map {_=>val v=d.pinsOut.peek().litValue;d.clk.step();v}
  test("MMIO byte strobes, all channel waveforms, ownership, decode and asynchronous reset") {
    simulateRaw(new Pwm(json)) { d=>
      init(d);assert(d.pinsEnable.peek().litValue==0)
      wr(d,0x40,0xabcd);wr(d,0x40,0x1234,1);assert(rd(d,0x40)==0xab34)
      wr(d,0xc0,0x1ffff);wr(d,0xc0,0,4);assert(rd(d,0xc0)==0xffff)
      for(i<-0 until 9) {wr(d,0x40+4*i,7);wr(d,0x80+4*i,2);wr(d,0xc0+4*i,i)}
      wr(d,0,511);assert(rd(d,8)==511 && high(d.clockHold))
      val waves=samples(d,24*5)
      for(i<-0 until 9) {
        assert(waves.count(_.testBit(i))==i*3*5,"PWM_HIGH_DURATION")
        assert(waves.drop(24)==waves.dropRight(24),"PWM_PERIOD_DURATION")
      }
      assert(access(d,4,true,511,origin=0)._2);assert(rd(d,8)==511)
      for(a<-Seq(3,0x24,0x100,0x140,0xffc)) assert(access(d,a,true,511)._2,"PWM_DECODE")
      assert(rd(d,8)==511)
      d.reset_n.poke(false.B)
      assert(d.pinsEnable.peek().litValue==0 && d.pinsOut.peek().litValue==0,"PWM_ASYNC_DISABLE")
      d.reset_n.poke(true.B);d.clk.step(10);assert(rd(d,8)==0 && rd(d,12)==0)
    }
  }
  test("queued configuration snapshot, invalid and busy updates, events and DMA") {
    simulateRaw(new Pwm(json)) { d=>
      init(d);wr(d,0x40,999);wr(d,0xc0,300);wr(d,0,1)
      wr(d,0x40,15);wr(d,0xc0,4);wr(d,0,1);assert(rd(d,12)==1)
      wr(d,0x40,3);wr(d,0xc0,1);wr(d,0,1)
      assert((rd(d,16)&512)!=0,"PWM_BUSY_UPDATE")
      d.clk.step(1100)
      val wave=samples(d,16*5);assert(wave.count(_.testBit(0))==4*5,"PWM_SNAPSHOT")
      assert(wave.drop(16)==wave.dropRight(16));assert(rd(d,12)==0)
      wr(d,0xc0,5);wr(d,0,1);assert(rd(d,12)==0,"PWM_INVALID_UPDATE")
      wr(d,0x14,1);d.clk.step(4);assert(high(d.irq))
      wr(d,0x18,1);d.clk.step(40);assert(d.dmaRequest.peek().litValue==1)
      assert((rd(d,16)&(1<<18))!=0,"PWM_DMA_OVERRUN")
      wr(d,0x18,0);assert(d.dmaRequest.peek().litValue==0)
      wr(d,4,1);assert(rd(d,8)==0 && rd(d,12)==0)
      wr(d,16,0x7ffffff);d.clk.step(4);assert(rd(d,16)==0 && !high(d.irq))
      wr(d,0x40,999);wr(d,0xc0,0);wr(d,0x18,1);wr(d,0,1)
      d.clk.step(1005);assert(d.dmaRequest.peek().litValue==1)
      wr(d,0x1c,1);assert(d.dmaRequest.peek().litValue==0,"PWM_SOFTWARE_DMA_ACK")
      d.clk.step(1005);assert(d.dmaRequest.peek().litValue==1)
      d.dmaAck.poke(1.U);d.clk.step();d.dmaAck.poke(0.U)
      assert(d.dmaRequest.peek().litValue==0,"PWM_EXTERNAL_DMA_ACK")
    }
  }
  test("DMA collisions follow a per-channel pending-event model; seed 22") {
    simulateRaw(new PwmDmaRequests) {d=>
      d.reset_n.poke(false.B);d.events.poke(0.U);d.mask.poke(0.U);d.acknowledge.poke(0.U);d.clk.step()
      d.reset_n.poke(true.B)
      var pending=Set.empty[Int];val random=new scala.util.Random(22)
      for(_<-0 until 1000) {
        val event=random.nextInt(512);val mask=random.nextInt(512);val ack=random.nextInt(512)
        val over=(0 until 9).filter(i=>pending(i) && ((event>>i)&1)==1 && ((mask>>i)&1)==1 && ((ack>>i)&1)==0).toSet
        pending=(0 until 9).filter(i=>((mask>>i)&1)==1 && (((event>>i)&1)==1 || (pending(i) && ((ack>>i)&1)==0))).toSet
        d.events.poke(event.U);d.mask.poke(mask.U);d.acknowledge.poke(ack.U);d.clk.step()
        assert(d.request.peek().litValue==pending.toSeq.map(1<<_).sum)
        assert(d.overrun.peek().litValue==over.toSeq.map(1<<_).sum)
      }
    }
  }
}
