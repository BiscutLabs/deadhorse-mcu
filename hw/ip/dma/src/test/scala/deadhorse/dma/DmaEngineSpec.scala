package deadhorse.dma
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import deadhorse.lib.LocalBus
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import scala.collection.mutable

class DmaEngineSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t23/engine-simulation").toAbsolutePath
  }
  val ep=DmaStandalone.endpoints;val base=DmaStandalone.memoryBase
  def high(b: Bool)=b.peek().litToBoolean
  case class Beat(addr: BigInt,write: Boolean,value: BigInt,mask: Int,origin: Int)
  class Model(d: DmaEngine,seed: Int=23) {
    val random=new scala.util.Random(seed)
    val ram=Array.tabulate(16384)(i=>(i*73+19)&255)
    val tx=mutable.Map.empty[Int,Vector[Int]].withDefaultValue(Vector.empty)
    val rx=mutable.Map.empty[Int,mutable.Queue[Int]]
    val applied=mutable.ArrayBuffer.empty[BigInt];var shadow=BigInt(0);var period=BigInt(999)
    var pendingPolls=0;var acknowledgements=0;var events=0;var errors=0;var cancels=0
    var offers=Vector.empty[(Boolean,Beat)];var granted=Vector.empty[(Boolean,Beat)]
    var grantEnabled=true;var failNext=false;var hints=BigInt(0x1ffff)
    var responseDelay: Option[Int]=None
    class Port(val b: LocalBus,val memory: Boolean) {
      var held: Option[Beat]=None;var response: Option[(Int,BigInt,Boolean)]=None
      def beat=Beat(b.bits.addr.peek().litValue,high(b.bits.we),b.bits.wdata.peek().litValue,
        b.bits.be.peek().litValue.toInt,b.bits.origin.peek().litValue.toInt)
      def before(): Unit={
        b.gnt.poke(false.B);b.rvalid.poke(false.B);b.rdata.poke(0.U);b.err.poke(false.B)
        response match {
          case Some((0,v,e))=>b.rvalid.poke(true.B);b.rdata.poke(v.U);b.err.poke(e.B);response=None
          case Some((n,v,e))=>response=Some((n-1,v,e))
          case None=>
        }
        if(high(b.req)) {
          val q=beat;held.foreach(old=>assert(q==old,"DMA_HELD_PAYLOAD"))
          if(held.isEmpty) {offers:+=memory->q;held=Some(q)}
          assert(q.origin==1 && q.addr%4==0,"DMA_PERMISSION")
          if(grantEnabled && random.nextInt(4)!=0) {
            assert(response.isEmpty && !high(b.rvalid),"DMA_DUPLICATE_OUTSTANDING")
            val error=failNext;failNext=false
            val value=if(error) BigInt(0) else transact(q,memory)
            granted:+=memory->q;b.gnt.poke(true.B);held=None
            response=Some((responseDelay.getOrElse(random.nextInt(4)),value,error))
          }
        } else assert(held.isEmpty,"DMA_WITHDREW_OFFER")
      }
    }
    val ports=Seq(new Port(d.memory,true),new Port(d.peripheral,false))
    def transact(q: Beat,memory: Boolean): BigInt={
      if(memory) {
        val off=(q.addr-base).toInt;assert(off>=0 && off+4<=ram.length)
        val value=(0 until 4).map(i=>BigInt(ram(off+i))<<(8*i)).reduce(_|_)
        if(q.write) for(i<-0 until 4 if (q.mask&(1<<i))!=0) ram(off+i)=((q.value>>(8*i))&255).toInt
        value
      } else {
        val selector=ep.data.indexOf(q.addr)
        if(selector>=0 && selector<8) {
          if(q.write) {assert(selector%2==0);tx(selector)=tx(selector):+(q.value&255).toInt;0}
          else {assert(selector%2==1 && rx(selector).nonEmpty);rx(selector).front}
        } else if(ep.command.take(8).contains(q.addr)) {
          val s=(1 until 8 by 2).find(i=>ep.command(i)==q.addr).get
          assert(q.write && q.value==ep.commandValue(s));rx(s).dequeue();0
        } else if(q.addr==ep.period.head) {assert(!q.write);period}
        else if(q.addr==ep.data(8)) {assert(q.write && q.mask==15);shadow=q.value;0}
        else if(q.addr==ep.pending) {assert(!q.write);if(pendingPolls>0) {pendingPolls-=1;1} else 0}
        else if(q.addr==ep.command(8)) {assert(q.write && q.value==1);applied+=shadow;pendingPolls=2;0}
        else fail(s"Unexpected DMA peripheral beat $q")
      }
    }
    def tick(n: Int=1): Unit=for(_<-0 until n) {
      d.requests.poke(hints.U);ports.foreach(_.before())
      events|=d.done.peek().litValue.toInt;errors|=d.failed.peek().litValue.toInt;cancels|=d.aborted.peek().litValue.toInt
      acknowledgements+=d.pwmAck.peek().litValue.bitCount;d.clk.step()
    }
    def init(): Unit={
      d.reset_n.poke(false.B);d.owner.poke(1.U);d.start.poke(0.U);d.abort.poke(0.U);d.requests.poke(0.U)
      d.settings.foreach(_.poke(0.U.asTypeOf(new DmaSettings)))
      ports.foreach {p=>p.b.gnt.poke(false.B);p.b.rvalid.poke(false.B);p.b.rdata.poke(0.U);p.b.err.poke(false.B)}
      d.clk.step(3);d.reset_n.poke(true.B)
    }
    def setup(i: Int,offset: Int,count: Int,endpoint: Int): Unit={
      d.settings(i).address.poke((base+offset).U);d.settings(i).count.poke(count.U);d.settings(i).endpoint.poke(endpoint.U)
    }
    def start(mask: Int): Unit={d.start.poke(mask.U);tick();d.start.poke(0.U)}
    def finish(): Unit={var n=0;while(d.busy.peek().litValue!=0) {tick();n+=1;assert(n<20000,"DMA_PROGRESS")};tick(3)}
    def word(offset: Int,value: Int): Unit=for(i<-0 until 4) ram(offset+i)=(value>>>(8*i))&255
  }
  test("four channels match packed-byte/PWM oracle with seeded stalls and transaction fairness") {
    simulateRaw(new DmaEngine(ep,base,DmaStandalone.memorySize,formalChecks=true)) {d=>
      val m=new Model(d);m.init()
      m.setup(0,1,23,0);m.setup(1,0x103,19,3);m.setup(2,0x200,3,8);m.setup(3,0x301,7,6)
      val expected0=m.ram.slice(1,24).toVector;val expected6=m.ram.slice(0x301,0x308).toVector
      val incoming=Vector.tabulate(19)(i=>(211-i*17)&255);m.rx(3)=mutable.Queue.from(incoming)
      val before=m.ram.clone();Seq(0,501,1000).zipWithIndex.foreach {case(v,i)=>m.word(0x200+4*i,v)}
      m.start(15);m.finish()
      assert(m.tx(0)==expected0 && m.tx(6)==expected6,"DMA_BYTE_ORACLE")
      assert(m.ram.slice(0x103,0x116).toVector==incoming && m.rx(3).isEmpty,"DMA_RX_ORACLE")
      assert(m.ram(0x102)==before(0x102) && m.ram(0x116)==before(0x116),"DMA_BYTE_LANES")
      assert(m.applied.toVector==Vector(0,501,1000).map(BigInt(_)) && m.acknowledgements==3,"DMA_PWM_ORACLE")
      assert(m.events==15 && m.errors==0 && m.cancels==0)
      Seq(24,0x116,0x20c,0x308).zipWithIndex.foreach {case(v,i)=>
        assert(d.current(i).peek().litValue==base+v && d.remaining(i).peek().litValue==0)}
      // While all channels are ready, the first four retired transactions serve each once.
      assert(m.granted.take(4).map(_._2.addr).toSet==Set(base,ep.data(3),base+0x200,base+0x300))
    }
  }
  test("descriptor rejection, abort before/after offer, errors and reset") {
    simulateRaw(new DmaEngine(ep,base,DmaStandalone.memorySize,formalChecks=true)) {d=>
      val m=new Model(d);m.init()
      for((offset,count,endpoint)<-Seq((0,0,0),(16383,2,0),(1,1,8),(0,1,17))) {
        m.setup(0,offset,count,endpoint);m.start(1);assert(d.rejected.peek().litValue==1 && d.busy.peek().litValue==0)
      }
      m.setup(0,0,1,0);d.owner.poke(0.U);m.start(1);assert(d.rejected.peek().litValue==1);d.owner.poke(1.U)
      m.setup(1,4,1,0);m.hints=0;m.start(3);assert(d.busy.peek().litValue==1 && d.rejected.peek().litValue==2)
      d.abort.poke(1.U);m.tick();d.abort.poke(0.U);assert(d.busy.peek().litValue==0);m.tick()
      m.cancels=0;m.hints=0x1ffff;m.grantEnabled=false;m.setup(0,1,2,0);m.start(1);m.tick(3)
      assert(high(d.memory.req));d.abort.poke(1.U);m.tick();d.abort.poke(0.U);m.tick(5)
      assert(high(d.memory.req) && d.busy.peek().litValue==1)
      m.grantEnabled=true;m.finish();assert(m.tx(0).size==1 && m.cancels==1 && d.remaining(0).peek().litValue==1)
      m.setup(0,8,1,0);m.failNext=true;m.start(1);m.finish();assert(m.errors==1 && d.fault(0).peek().litValue==1)
      m.word(0x200,1001);m.setup(0,0x200,1,8);m.start(1);m.finish()
      assert(d.fault(0).peek().litValue==9 && m.applied.isEmpty,"DMA_INVALID_PWM")
      m.grantEnabled=false;m.setup(0,0,1,0);m.start(1);m.tick(3)
      d.reset_n.poke(false.B);assert(!high(d.memory.req) && d.busy.peek().litValue==0,"DMA_ASYNC_RESET")
    }
  }
  class Corrupt extends DmaEngine(ep,base,DmaStandalone.memorySize) {
    override protected def copied(v: UInt): UInt=v^1.U
  }
  test("abort drains every TX/RX/PWM offered or waiting phase and terminal collision") {
    simulateRaw(new DmaEngine(ep,base,DmaStandalone.memorySize,formalChecks=true)) {d=>
      for((selector,phases)<-Seq(0->2,1->3,8->5);phase<-1 to phases;atOffer<-Seq(true,false)) {
        val m=new Model(d,100+phase);m.init();m.responseDelay=Some(3);m.rx(1)=mutable.Queue(0x5a,0xa5)
        if(selector==8) m.word(0,123)
        m.setup(0,0,2,selector);m.start(1)
        var n=0
        if(atOffer) {
          while(m.granted.size<phase-1) {m.tick();n+=1;assert(n<300)}
          m.grantEnabled=false
          while(!high(d.memory.req) && !high(d.peripheral.req)) {m.tick();n+=1;assert(n<300)}
        } else while(m.granted.size<phase) {m.tick();n+=1;assert(n<300)}
        d.abort.poke(1.U);m.tick();d.abort.poke(0.U);if(atOffer) m.tick(3)
        m.grantEnabled=true;m.finish()
        assert(m.cancels==1 && m.events==0 && m.errors==0 && d.remaining(0).peek().litValue==1,"DMA_ABORT_DRAIN")
        assert(m.granted.size==phases,"DMA_ABORT_ONE_ITEM")
      }
      val m=new Model(d);m.init();m.responseDelay=Some(3);m.setup(0,0,1,0);m.start(1)
      var n=0;while(m.granted.size<2 || !m.ports(1).response.exists(_._1==0)) {m.tick();n+=1;assert(n<100)}
      d.abort.poke(1.U);d.start.poke(1.U);m.tick();d.abort.poke(0.U);d.start.poke(0.U);m.tick(3)
      assert(m.cancels==1 && m.events==0 && d.busy.peek().litValue==0,"DMA_TERMINAL_ABORT_WINS")
    }
  }
  test("RX partial store is not replayed on POP error and stale TX readiness waits") {
    simulateRaw(new DmaEngine(ep,base,DmaStandalone.memorySize,formalChecks=true)) {d=>
      val m=new Model(d);m.init();m.rx(1)=mutable.Queue(0x37);m.setup(0,3,1,1);m.start(1)
      var n=0;while(!(high(d.peripheral.req) && d.peripheral.bits.addr.peek().litValue==ep.command(1))) {
        m.tick();n+=1;assert(n<100)
      }
      m.failNext=true;d.abort.poke(1.U);m.tick();d.abort.poke(0.U);m.finish()
      assert(m.ram(3)==0x37 && m.rx(1).toVector==Vector(0x37),"DMA_PARTIAL_SIDE_EFFECT")
      assert(m.errors==1 && m.cancels==0 && d.remaining(0).peek().litValue==1 && d.fault(0).peek().litValue==4)
      assert(m.granted.count {case(mem,b)=>mem && b.write}==1,"DMA_NO_REPLAY")
      val t=new Model(d);t.init();t.setup(0,0,1,0);t.start(1)
      while(t.granted.isEmpty) t.tick()
      t.hints=0;t.tick(20);assert(t.tx(0).isEmpty && d.busy.peek().litValue==1,"DMA_TX_WAIT_HINT")
      t.hints=1;t.finish();assert(t.tx(0)==Vector(t.ram(0)))
    }
  }
  test("deliberate RTL data corruption fails the independent byte oracle") {
    val caught=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new Corrupt) {d=>val m=new Model(d);m.init();val expected=m.ram(0)
        m.setup(0,0,1,0);m.start(1);m.finish();assert(m.tx(0)==Vector(expected),"DMA_BYTE_ORACLE")}
    }
    assert(caught.getMessage.contains("DMA_BYTE_ORACLE"))
  }
}
