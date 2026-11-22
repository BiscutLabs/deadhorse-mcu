package deadhorse.qspi
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Independent symbol stream built from the software transaction, checked
  * exclusively at pads and MMIO. Input data is launched on falling edges. */
class QspiSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t29/wire-simulation").toAbsolutePath
  }
  case class Symbol(enable: Int,out: Int,in: Int)
  def symbols(value: Long,bytes: Int,quad: Boolean,read: Boolean=false): Vector[Symbol]={
    val width=if(quad)4 else 1
    (0 until bytes*8/width).map {n=>
      val v=((value>>>(bytes*8-width*(n+1)))&((1<<width)-1)).toInt
      if(read) Symbol(if(quad)0 else 12,12,if(quad)v else v<<1)
      else Symbol(if(quad)15 else 13,if(quad)v else 12|v,0)
    }.toVector
  }
  def exercise(d: Qspi): Unit={
    def value(v: UInt)=v.peek().litValue.toInt
    def high(v: Bool)=v.peek().litToBoolean
    var expected=Vector.empty[Symbol];var index=0;var running=false;var ended=false
    var selected=0;var half=4;var cycle=0;var edgeCycle=0;var csCycle=0
    var previousCs=3;var previousClock=false
    var awaiting=false;var launchCycle=0
    def tick(n: Int=1): Unit=for(_<-0 until n) {
      d.dqIn.poke((if(running && index<expected.size) expected(index).in else 0).U)
      d.clk.step();cycle+=1
      if(awaiting) assert(cycle-launchCycle<=53299,"QSPI_COMPLETION_BOUND")
      val cs=value(d.cs_n);val clock=high(d.sclk)
      if(previousCs==3 && cs!=3) {
        assert(expected.nonEmpty && !running,"QSPI_UNEXPECTED_START")
        running=true;index=0;edgeCycle=cycle;csCycle=cycle
        assert(cs==(if(selected==0)2 else 1),"QSPI_SELECT")
      }
      if(clock!=previousClock) {
        assert(running && cs!=3 && cycle-edgeCycle==half,"QSPI_EDGE_SPACING")
        edgeCycle=cycle
        if(clock) {
          assert(index<expected.size,"QSPI_EXTRA_CLOCK")
          val s=expected(index)
          assert(value(d.dqEnable)==s.enable,"QSPI_DIRECTION")
          assert((value(d.dqOut)&s.enable)==(s.out&s.enable),"QSPI_WIRE_DATA")
        } else index+=1
      }
      if(previousCs!=3 && cs==3) {
        assert(index==expected.size && !clock && cycle-edgeCycle==half,"QSPI_FRAME_END")
        assert(value(d.dqEnable)==0);ended=true;running=false;csCycle=cycle
      }
      if(cs!=3 || (awaiting && ended && cycle-csCycle<half)) assert(high(d.clockHold),"QSPI_CLOCK_HOLD")
      previousCs=cs;previousClock=clock
    }
    d.reset_n.poke(false.B);d.bus.req.poke(false.B);d.bus.bits.poke(0.U.asTypeOf(d.bus.bits));d.dqIn.poke(0.U)
    d.clk.step(3);d.reset_n.poke(true.B);tick(3)
    def access(a: Int,w: Boolean=false,v: Long=0,be: Int=15,origin: Int=0): (BigInt,Boolean)={
      d.bus.req.poke(true.B);d.bus.bits.addr.poke(a.U);d.bus.bits.we.poke(w.B)
      d.bus.bits.wdata.poke(v.U);d.bus.bits.be.poke(be.U);d.bus.bits.origin.poke(origin.U)
      var n=0
      while(!high(d.bus.gnt)) {tick();n+=1;assert(n<32)}
      tick();d.bus.req.poke(false.B)
      while(!high(d.bus.rvalid)) {tick();n+=1;assert(n<32)}
      val r=(d.bus.rdata.peek().litValue,high(d.bus.err));tick(2);r
    }
    def wr(a: Int,v: Long,origin: Int=0): Unit=assert(!access(a,true,v,origin=origin)._2)
    def rd(a: Int,origin: Int=0): BigInt={val(v,e)=access(a,origin=origin);assert(!e);v}
    assert(rd(28)==0 && value(d.csEnable)==0 && !high(d.sclkEnable))
    for(o<-1 to 7) assert(access(20,true,0x51535049L,origin=o)._2,"QSPI_OWNER")
    for(a<-Seq(1,40,4096)) assert(access(a)._2)
    for(be<-1 to 14) assert(access(20,true,0x51535049L,be=be)._2)
    assert(!access(20,true,0x51535049L,be=0)._2 && rd(32)==0)
    wr(20,0);assert(rd(32)==2);wr(32,3)
    wr(0,7<<1);wr(20,0x51535049L);assert(rd(32)==2);wr(32,3)
    wr(0,0);wr(4,3);wr(20,0x51535049L);assert(rd(32)==2);wr(32,3)
    val random=new scala.util.Random(0x29)
    for(test<-0 until 25) {
      val ab=test%5;val db=(test/5)%5;val qa=(test&1)!=0;val qd=(test&2)!=0;val read=(test&4)!=0
      selected=test&1;half=if(test==24)255 else 4+test%3
      val dummy=if(test==24)31 else test%4;val op=0x80+test
      val address=random.nextInt().toLong&0xffffffffL;val tx=random.nextInt().toLong&0xffffffffL
      val rx=random.nextInt().toLong&0xffffffffL
      wr(0,selected|(ab<<1)|(db<<4)|(if(read)128 else 0)|(if(qa)256 else 0)|(if(qd)512 else 0))
      wr(4,half|(dummy<<8));wr(8,op);wr(12,address);wr(16,tx)
      expected=symbols(op,1,false)++symbols(address,ab,qa)++Vector.fill(dummy)(Symbol(0,0,0))++symbols(if(read)rx else tx,db,qd,read)
      ended=false;awaiting=true;launchCycle=cycle;wr(20,0x51535049L)
      if(test==1) {
        wr(20,0x51535049L);wr(36,0x4f574e01L);wr(8,0);wr(12,0);wr(16,0);wr(4,255)
        assert((rd(32)&2)!=0 && (rd(28)&14)==0,"QSPI_BUSY_REJECT")
      }
      while(!ended || (rd(28)&1)!=0) tick()
      awaiting=false
      assert(cycle-csCycle>=half,"QSPI_GAP")
      assert((rd(32)&1)!=0,"QSPI_DONE")
      val mask=if(db==4)0xffffffffL else (1L<<(db*8))-1
      assert(rd(24)==(if(read)rx&mask else 0L),"QSPI_RX_DATA")
      wr(32,3);assert(rd(32)==0)
      assert(!high(d.clockHold));expected=Vector.empty
    }
    // Owner change returns a response to the old owner and preserves settings.
    val old=rd(8);wr(36,0x4f574e01L)
    assert(access(8)._2,"QSPI_OLD_OWNER");assert(rd(8,1)==old && rd(28,1)==2)
    wr(36,0x4f574e00L,1);assert(rd(28)==0)
    wr(36,0x4f574e02L);assert(rd(28)==0 && rd(32)==2)
    // Abort a selected flash with no subsequent controller clock edge.
    wr(0,0);wr(4,255);wr(8,6);expected=symbols(6,1,false);half=255;selected=0
    wr(20,0x51535049L);assert(value(d.cs_n)==2)
    d.reset_n.poke(false.B)
    assert(value(d.cs_n)==3 && value(d.dqEnable)==0 && value(d.csEnable)==0 && !high(d.sclkEnable),"QSPI_ASYNC_RESET")
    running=false;ended=false;expected=Vector.empty;previousCs=3;previousClock=false
    tick(2);d.reset_n.poke(true.B);tick(5);assert(rd(28)==0 && rd(32)==0)
  }
  test("single/quad symbols, turnaround, bounded gap, snapshot, ownership and reset") {
    simulateRaw(new Qspi("build/t29/qspi/qspi_regs.json"))(exercise)
  }
  test("actual transmit bit fault is rejected by wire oracle") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new Qspi("build/t29/qspi/qspi_regs.json") {
        override protected def engine(): QspiEngine=new QspiEngine {
          override protected def transmit(v: UInt): UInt=v^1.U
        }
      })(exercise)
    };assert(e.getMessage.contains("QSPI_WIRE_DATA"))
  }
}
