package deadhorse.aon_spi

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class AonSpiSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan05/aon-spi/simulation").toAbsolutePath
  }
  private def exercise(d: AonSpi): Unit={
    def high(v: Bool)=v.peek().litToBoolean
    var selected=false;var previousClock=false;var bits=0;var word=0
    var offered=Vector.empty[Int];var observed=Vector.empty[Int];var frameLengths=Vector.empty[Int]
    var frameBytes=0
    var cycles=0;var lastEdge=0;var expectedDivider=1
    val radio=Vector(0x81,0x42,0x24,0x18,0xe7,0x5a,0xa5,0xff)
    def inputBit(): Unit={
      val b=radio((bits/8)%radio.size)
      d.miso.poke(((b & (1 << (7-bits%8)))!=0).B)
    }
    def tick(n: Int=1): Unit=for(_<-0 until n) {
      d.clk.step();cycles+=1
      val cs= !high(d.cs_n);val ck=high(d.sclk)
      if(cs && !selected) {bits=0;word=0;frameBytes=0;lastEdge=cycles;inputBit()}
      if(cs && selected && ck!=previousClock) {
        assert(cycles-lastEdge==expectedDivider,"SPI_EDGE_SPACING");lastEdge=cycles
      }
      if(cs && selected && !previousClock && ck) {
        word=(word<<1)|(if(high(d.mosi)) 1 else 0);bits+=1
        if(bits%8==0) {observed :+= word;word=0;frameBytes+=1}
      }
      if(cs && selected && previousClock && !ck) inputBit()
      if(!cs && selected) {assert(bits%8==0,"SPI_CS_PARTIAL");frameLengths :+= frameBytes}
      selected=cs;previousClock=ck
    }
    d.reset_n.poke(false.B);d.bus.req.poke(false.B)
    d.bus.bits.addr.poke(0.U);d.bus.bits.we.poke(false.B);d.bus.bits.wdata.poke(0.U)
    d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(0.U);d.miso.poke(false.B)
    tick(4);d.reset_n.poke(true.B);tick(4)
    def access(a: Int,write: Boolean=false,value: Int=0,origin: Int=0): (Int,Boolean)={
      d.bus.req.poke(true.B);d.bus.bits.addr.poke(a.U);d.bus.bits.we.poke(write.B)
      d.bus.bits.wdata.poke(value.U);d.bus.bits.origin.poke(origin.U)
      var n=0
      while(!high(d.bus.gnt)) {tick();n+=1;assert(n<32,"SPI_GRANT")}
      tick();d.bus.req.poke(false.B)
      while(!high(d.bus.rvalid)) {tick();n+=1;assert(n<32,"SPI_REPLY")}
      val result=(d.bus.rdata.peek().litValue.toInt,high(d.bus.err));tick(2);result
    }
    def wr(a: Int,v: Int): Unit=assert(!access(a,true,v)._2,s"SPI_WRITE $a")
    def rd(a: Int): Int={val(v,e)=access(a);assert(!e,s"SPI_READ $a");v}
    assert(access(12)._2,"SPI_EMPTY")
    assert(access(0,true,1,origin=1)._2,"SPI_OWNER")
    for(mode<-Seq(0,3); divider<-Seq(1,3); length<-Seq(1,3,8)) {
      expectedDivider=divider
      wr(0,if(mode==3) 3 else 1);wr(16,divider);wr(20,length);wr(28,3);wr(32,3)
      val tx=Vector.tabulate(length)(i=>(i*37+0x53)&255)
      tx.foreach(v=>wr(8,v));offered++=tx
      val before=observed.size;val framesBefore=frameLengths.size
      wr(24,1)
      if(length==8) {
        assert(access(16,true,7)._2,"SPI_BUSY_CONFIG")
        assert(rd(16)==divider,"SPI_CONFIG_CHANGED")
      }
      var n=0
      while((rd(4)&1)!=0) {n+=1;assert(n<128,"SPI_DONE")}
      assert(frameLengths.size==framesBefore+1 && frameLengths.last==length,"SPI_CS_FRAME")
      assert(observed.drop(before)==tx,"SPI_TX_ORDER")
      assert((rd(28)&1)==1 && high(d.irq),"SPI_COMPLETE_IRQ")
      assert((rd(4)>>8)==length,"SPI_RX_COUNT")
      assert(Vector.fill(length)(rd(12))==radio.take(length),"SPI_RX_ORDER")
      assert(access(12)._2,"SPI_UNDERFLOW")
      wr(28,3)
    }
    assert(observed==offered)
    expectedDivider=3;wr(0,1);wr(16,3);wr(20,3);wr(28,3)
    wr(8,0x11);wr(8,0x22);wr(24,1)
    assert(high(d.cs_n) && (rd(28)&2)!=0 && ((rd(4)>>4)&15)==2,"SPI_SHORT_TX")
    wr(8,0x33);val beforeConcurrent=observed.size;wr(24,1)
    wr(8,0x44) // Queue the next frame while this one is shifting.
    var receiveGuard=0
    while((rd(4)>>8)==0) {receiveGuard+=1;assert(receiveGuard<128,"SPI_RX_WAIT")}
    assert((rd(4)&1)!=0,"SPI_CONCURRENT_PRECONDITION")
    assert(rd(12)==radio(0),"SPI_CONCURRENT_RX")
    var guard=0
    while((rd(4)&1)!=0) {guard+=1;assert(guard<128)}
    assert(observed.drop(beforeConcurrent)==Vector(0x11,0x22,0x33),"SPI_TX_ORDER")
    assert(Vector(rd(12),rd(12))==radio.slice(1,3),"SPI_RX_ORDER")
    assert(((rd(4)>>4)&15)==1,"SPI_CONCURRENT_TX")
    wr(20,1);wr(24,1)
    guard=0;while((rd(4)&1)!=0) {guard+=1;assert(guard<128)}
    assert(observed.last==0x44 && rd(12)==radio(0),"SPI_QUEUED_FRAME")
    expectedDivider=1;wr(16,1);wr(20,8)
    for(i<-0 until 8) wr(8,i)
    wr(24,1);guard=0;while((rd(4)&1)!=0) {guard+=1;assert(guard<128)}
    wr(20,1);wr(8,0x66);wr(28,3);val fullFrames=frameLengths.size;wr(24,1)
    assert(high(d.cs_n) && frameLengths.size==fullFrames && (rd(28)&2)!=0,"SPI_RX_CAPACITY")
    assert(Vector.fill(8)(rd(12))==radio,"SPI_RX_ORDER")
    wr(0,0);wr(24,1);assert((rd(28)&2)!=0 && high(d.cs_n),"SPI_DISABLED_START")
    wr(0,1);wr(16,0);wr(24,1);assert(high(d.cs_n),"SPI_ZERO_DIVIDER")
    for(i<-0 until 7) wr(8,i) // One byte remains queued after the rejected start.
    assert(access(8,true,0x99)._2,"SPI_OVERFLOW")
    d.reset_n.poke(false.B);tick(2);assert(high(d.cs_n) && !high(d.pinsEnable))
  }
  test("mode 0/3 framed FIFO transfers, minimum divider, permissions and invalid accesses") {
    simulateRaw(new AonSpi("build/plan05/aon_spi/aon_spi_regs.json"))(exercise)
  }
  test("wire oracle rejects corrupt MOSI") {
    val error=intercept[Throwable] {
      simulateRaw(new AonSpi("build/plan05/aon_spi/aon_spi_regs.json") {
        override protected def transmit(value: Bool): Bool= !value
      })(exercise)
    }
    assert(Iterator.iterate(error)(_.getCause).takeWhile(_!=null).exists(e=>Option(e.getMessage).exists(_.contains("SPI_TX_ORDER"))))
  }
  test("wire oracle rejects corrupt received byte") {
    val error=intercept[Throwable] {
      simulateRaw(new AonSpi("build/plan05/aon_spi/aon_spi_regs.json") {
        override protected def receive(value: UInt): UInt=value ^ 1.U
      })(exercise)
    }
    assert(Iterator.iterate(error)(_.getCause).takeWhile(_!=null).exists(e=>Option(e.getMessage).exists(_.contains("SPI_RX_ORDER"))))
  }
}
