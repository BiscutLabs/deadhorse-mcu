package deadhorse.dma
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import deadhorse.lib.LocalBus
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class DmaCircularProbe extends Dma("build/t23/dma/dma_regs.json",DmaStandalone.endpoints,
  DmaStandalone.memoryBase,DmaStandalone.memorySize) {
  val registerWrite=IO(Output(Bool()));registerWrite:=regs.bus.req_valid && regs.bus.req_ready && regs.bus.req_write
  val wrapPulse=IO(Output(UInt(4.W)));wrapPulse:=engine.wrap
}
class DmaCircularMmioSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t40/mmio-simulation").toAbsolutePath
  }
  val ep=DmaStandalone.endpoints;val base=DmaStandalone.memoryBase
  def design(brokenLock: Boolean=false)=new Dma("build/t23/dma/dma_regs.json",ep,base,DmaStandalone.memorySize) {
    override protected def shadowLocked(v: Bool): Bool=if(brokenLock) false.B else v
  }
  class Host(d: Dma) {
    var hints=0;var ticks=0;var pops=0;var writes=Vector.empty[(BigInt,Int,BigInt)]
    var blockPop=false;var beforeEdge: ()=>Unit=()=>()
    class Port(p: LocalBus,mem: Boolean) {
      var pending=false;var pendingPop=false
      def before(): Unit={
        val held=pending && pendingPop && blockPop
        p.gnt.poke(true.B);p.rvalid.poke((pending && !held).B);p.err.poke(false.B);p.rdata.poke(0x5a.U)
        val accepted=p.req.peek().litToBoolean
        pending=held || accepted
        if(accepted) {
          val addr=p.bits.addr.peek().litValue
          pendingPop= !mem && p.bits.we.peek().litToBoolean && ep.command.take(8).contains(addr)
          if(mem && p.bits.we.peek().litToBoolean) writes:+=((addr,p.bits.be.peek().litValue.toInt,p.bits.wdata.peek().litValue))
          if(!mem && p.bits.we.peek().litToBoolean && ep.command.take(8).contains(addr)) pops+=1
        }
      }
    }
    val ports=Seq(new Port(d.memory,true),new Port(d.peripheral,false))
    def step(n: Int=1): Unit=for(_<-0 until n) {beforeEdge();d.requests.poke(hints.U);ports.foreach(_.before());d.clk.step();ticks+=1}
    def init(): Unit={
      d.reset_n.poke(false.B);d.owner.poke(1.U);d.bus.req.poke(false.B)
      d.bus.bits.poke(0.U.asTypeOf(d.bus.bits));step(3);d.reset_n.poke(true.B);step(3)
    }
    def access(a: Int,write: Boolean=false,value: BigInt=0,be: Int=15,origin: Int=1): BigInt={
      d.bus.bits.addr.poke(a.U);d.bus.bits.we.poke(write.B);d.bus.bits.wdata.poke(value.U)
      d.bus.bits.be.poke(be.U);d.bus.bits.origin.poke(origin.U);d.bus.req.poke(true.B)
      var n=0
      while(!d.bus.gnt.peek().litToBoolean) {step();n+=1;assert(n<100)}
      step();d.bus.req.poke(false.B)
      while(!d.bus.rvalid.peek().litToBoolean) {step();n+=1;assert(n<100)}
      assert(d.bus.err.peek().litToBoolean==(origin!=1 || a%4!=0),"RING_MMIO_RESPONSE")
      val v=d.bus.rdata.peek().litValue;step();v
    }
    def wr(a: Int,v: BigInt,be: Int=15): Unit={access(a,true,v,be);()}
    def rd(a: Int): BigInt=access(a)
    def configure(i: Int,ring: Boolean,count: Int=5): Unit={
      wr(0x20+4*i,base+0x101+0x100*i);wr(0x30+4*i,count);wr(0x40+4*i,(1+2*(i%3))|(if(ring)32 else 0))
    }
  }
  def lockCheck(d: Dma): Unit={
    val h=new Host(d);h.init()
    for(i<-0 until 4) {
      h.configure(i,true);val old=Seq(0x20,0x30,0x40).map(a=>h.rd(a+4*i))
      h.wr(0,1<<i);assert(h.rd(8)==(1<<i))
      for((a,v)<-Seq(0x20->(base+0x900),0x30->BigInt(2),0x40->BigInt(0))) {
        h.wr(12,0xffffff);h.wr(a+4*i,v)
        assert(h.rd(a+4*i)==old(Seq(0x20,0x30,0x40).indexOf(a)),"RING_BUSY_SHADOW_CHANGED")
        assert(h.rd(12)==(BigInt(1)<<(8+i)),"RING_SHADOW_CONFIG_ERROR")
      }
      h.wr(12,0xffffff);h.wr(0x20+4*i,0,be=0);assert(h.rd(12)==0,"RING_ZERO_STROBE")
      h.access(0x30+4*i,true,2,origin=7);assert(h.rd(12)==0,"RING_DENIED_NO_EFFECT")
      h.wr(4,1<<i);assert(h.rd(8)==0)
      h.wr(0x20+4*i,base+0x900);h.wr(0x30+4*i,2);h.wr(0x40+4*i,0)
      assert(h.rd(0x20+4*i)==base+0x900 && h.rd(0x30+4*i)==2 && h.rd(0x40+4*i)==0)
    }
  }
  test("busy circular shadows lock on all channels, denied/zero-strobe writes are inert and abort unlocks") {
    simulateRaw(design()) {d=>lockCheck(d)}
  }
  test("shadow-lock oracle rejects accepted busy write") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {simulateRaw(design(true)) {d=>lockCheck(d)}}
    assert(e.getMessage.contains("RING_BUSY_SHADOW_CHANGED"))
  }
  test("non-circular active shadows remain writable including a next-START circular bit") {
    simulateRaw(design()) {d=>
      val h=new Host(d);h.init();h.configure(0,false);h.wr(0,1)
      h.wr(0x40,33);h.wr(0x20,base+0x900);h.wr(0x30,7)
      assert(h.rd(0x20)==base+0x900 && h.rd(0x30)==7 && h.rd(0x40)==33)
      assert(h.rd(0x60)==base+0x101 && h.rd(0x50)==5 && h.rd(12)==0,"RING_SHADOW_MODE_NOT_ACTIVE")
      h.wr(4,1);h.wr(0,1);h.wr(0x30,9)
      assert(h.rd(0x50)==7 && h.rd(0x30)==7 && (h.rd(12)&0x100)!=0)
    }
  }
  test("half/wrap sticky events, masks and W1C work while circular mode never sets done") {
    simulateRaw(design()) {d=>
      val h=new Host(d);h.init();h.configure(0,true,count=5);h.wr(0x10,0x110000);h.wr(0,1)
      for(lap<-0 until 3) {
        // Admit one byte at a time, so status is cleared before the next lap.
        for(item<-1 to 5) {
          h.hints=2;val target=h.pops+1;var n=0
          while(h.pops<target) {h.step();n+=1;assert(n<100)}
          h.hints=0;h.step(3)
          val status=h.rd(12)
          val expected=if(item==5)0x110000 else if(item>=3)0x10000 else 0
          assert(status==expected,"RING_STICKY_EVENTS")
          assert(h.rd(0x60)==base+0x101+(item%5),"RING_MMIO_CURSOR")
          assert(d.irq.peek().litToBoolean==(item>=3),"RING_IRQ_MASK")
        }
        h.wr(12,0x110000);h.step(3);assert(h.rd(12)==0 && !d.irq.peek().litToBoolean)
      }
      h.wr(4,1);assert(h.rd(8)==0 && h.writes.size==15)
    }
  }
  test("terminal POP shadow collision rejects the write and event set wins simultaneous W1C") {
    simulateRaw(new DmaCircularProbe) {d=>
      val h=new Host(d);h.init();h.configure(0,true,count=2);h.wr(0,1)
      for(clear<-Seq(false,true)) {
        h.hints=2;h.blockPop=false
        val target=h.pops+2;var n=0
        // Hold only the final POP response, after its request is accepted.
        while(h.pops<target) {
          h.step();n+=1;assert(n<200,"RING_TERMINAL_REACHABLE")
        }
        h.blockPop=true
        h.hints=0;var collided=false
        h.beforeEdge=()=> {
          // Shadow collision: release POP on register acceptance. For W1C,
          // release it on the preceding local-bus acceptance so the registered
          // wrap pulse coincides with the register's W1C acceptance edge.
          if(if(clear) d.bus.req.peek().litToBoolean && d.bus.gnt.peek().litToBoolean
             else d.registerWrite.peek().litToBoolean) h.blockPop=false
          if(d.registerWrite.peek().litToBoolean) {
            collided=if(clear) d.wrapPulse.peek().litValue==1 else !h.blockPop
          }
        }
        if(clear) h.wr(12,0x110000) else h.wr(0x20,base+0x900)
        h.beforeEdge=()=>();assert(collided,"RING_REAL_COLLISION")
        assert(h.rd(0x20)==base+0x101 && h.rd(0x60)==base+0x101,"RING_COLLISION_RELOAD")
        if(clear) assert((h.rd(12)&0x100000)!=0,"RING_W1C_SET_PRIORITY")
        else {assert((h.rd(12)&0x100)!=0,"RING_TERMINAL_WRITE_REJECTED");h.wr(12,0xffffff)}
      }
      h.wr(4,1)
    }
  }
}
