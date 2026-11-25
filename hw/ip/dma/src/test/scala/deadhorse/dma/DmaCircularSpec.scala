package deadhorse.dma
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import scala.collection.mutable

class DmaCircularSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t40/circular-simulation").toAbsolutePath
  }
  val existing=new DmaEngineSpec
  val ep=DmaStandalone.endpoints;val base=DmaStandalone.memoryBase
  def engine(mutation: String=""): DmaEngine=new DmaEngine(ep,base,DmaStandalone.memorySize,formalChecks=true) {
    override protected def reloadAddress(v: UInt): UInt=if(mutation=="reload") v+1.U else v
    override protected def halfItem(n: UInt,c: UInt): Bool=if(mutation=="half") n===((c>>1)+1.U) else super.halfItem(n,c)
    override protected def terminalDone(r: Bool): Bool=if(mutation=="done") true.B else super.terminalDone(r)
  }
  def laps(d: DmaEngine,count: Int,selector: Int): Unit={
    val m=new existing.Model(d,40+count);m.init()
    val start=0x103;val input=Vector.tabulate(count*3)(i=>(i*29+71)&255)
    m.rx(selector)=mutable.Queue.from(input)
    m.setup(0,start,count,selector);d.settings(0).circular.poke(true.B)
    m.setup(1,0x300,9,0);val tx=m.ram.slice(0x300,0x309).toVector
    val untouched=m.ram.clone();m.start(3)
    var completed=0;var previous=base+start;var ticks=0;var halfs=0;var wraps=0
    while(completed<count*3) {
      m.hints=1 | (if(m.rx(selector).nonEmpty) 1<<selector else 0)
      m.tick();ticks+=1;assert(ticks<12000,"RING_PROGRESS")
      val cursor=d.current(0).peek().litValue
      val half=d.half.peek().litValue.testBit(0);val wrap=d.wrap.peek().litValue.testBit(0)
      assert(!d.done.peek().litValue.testBit(0),"RING_NO_DONE")
      if(cursor!=previous) {
        completed+=1
        val index=completed%count
        assert(cursor==base+start+index,"RING_RELOAD_ADDRESS")
        assert(d.remaining(0).peek().litValue==(if(index==0) count else count-index),"RING_REMAINING")
        assert(half==(index==(count+1)/2),"RING_HALF_ITEM")
        assert(wrap==(index==0),"RING_WRAP_ITEM")
        assert(d.peripheral.rvalid.peek().litToBoolean && !d.peripheral.err.peek().litToBoolean,"RING_PUBLISH_AFTER_POP")
        val byte=(completed-1)%count
        assert(m.ram(start+byte)==input(completed-1),"RING_COMMITTED_BYTE")
        previous=cursor
      } else assert(!half && !wrap,"RING_SPURIOUS_EVENT")
      if(half) halfs+=1
      if(wrap) wraps+=1
    }
    assert(halfs==3 && wraps==3 && m.errors==0,"RING_LAP_EVENTS")
    assert(m.ram.slice(start,start+count).toVector==input.takeRight(count),"RING_FINAL_BYTES")
    assert(m.ram(start-1)==untouched(start-1) && m.ram(start+count)==untouched(start+count),"RING_BOUNDS")
    d.abort.poke(1.U);m.tick();d.abort.poke(0.U);m.finish()
    assert(m.tx(0)==tx,"RING_PEER_NOT_STARVED")
    assert(!d.busy.peek().litValue.testBit(0))
  }
  test("three laps at counts 2,5,8 on every UART RX preserve exact bytes, pulses and peer service") {
    simulateRaw(engine()) {d=>for((count,sel)<-Seq(2->1,5->3,8->5)) laps(d,count,sel)}
  }
  test("circular START rejects TX, SPI, timer, invalid endpoints and counts below two") {
    simulateRaw(engine()) {d=>
      val m=new existing.Model(d);m.init();m.hints=0
      for(sel<-Seq(0,2,4,6,7)++(8 to 31)) {
        m.setup(0,0,3,sel);d.settings(0).circular.poke(true.B);m.start(1)
        assert(d.rejected.peek().litValue==1 && d.busy.peek().litValue==0,"RING_BAD_SELECTOR")
      }
      for(n<-Seq(0,1)) {m.setup(0,0,n,1);m.start(1);assert(d.rejected.peek().litValue==1 && d.busy.peek().litValue==0)}
    }
  }
  test("ABORT on the half or wrap POP completes only that item and fault does not publish it") {
    simulateRaw(engine()) {d=>
      for((count,stopAt)<-Seq(5->3,2->2);fault<-Seq(false,true)) {
        val m=new existing.Model(d);m.init();m.responseDelay=Some(3)
        m.rx(1)=mutable.Queue.from(Seq(11,22,33,44,55,66));m.setup(0,0x100,count,1)
        d.settings(0).circular.poke(true.B);m.start(1)
        var n=0
        while(m.granted.count {case(mem,q)=> !mem && q.write && q.addr==ep.command(1)}<stopAt-1) {m.tick();n+=1;assert(n<1000)}
        // Stop granting before the final POP; all preceding store work is real.
        while(!(d.peripheral.req.peek().litToBoolean && d.peripheral.bits.we.peek().litToBoolean &&
          d.peripheral.bits.addr.peek().litValue==ep.command(1))) {m.tick();n+=1;assert(n<1500)}
        m.failNext=fault;d.abort.poke(1.U)
        var sawHalf=false;var sawWrap=false;var sawDone=false
        while(d.busy.peek().litValue!=0) {
          m.tick();n+=1;assert(n<2000)
          sawHalf ||= d.half.peek().litValue.testBit(0)
          sawWrap ||= d.wrap.peek().litValue.testBit(0)
          sawDone ||= d.done.peek().litValue.testBit(0)
        }
        d.abort.poke(0.U);m.tick()
        assert(!sawWrap && !sawDone,"RING_ABORT_SUPPRESSES_RELOAD")
        assert(sawHalf==(!fault && stopAt==(count+1)/2),"RING_ABORT_HALF")
        val retired=stopAt-(if(fault) 1 else 0)
        assert(d.current(0).peek().litValue==base+0x100+retired && d.remaining(0).peek().litValue==count-retired,"RING_ABORT_CURSOR")
        assert(if(fault) m.errors==1 && m.cancels==0 else m.cancels==1 && m.errors==0)
      }
    }
  }
  for((fault,diagnostic)<-Seq("reload"->"RING_RELOAD_ADDRESS","half"->"RING_HALF_ITEM","done"->"RING_NO_DONE")) {
    test(s"circular oracle rejects actual $fault fault") {
      val e=intercept[org.scalatest.exceptions.TestFailedException] {simulateRaw(engine(fault)) {d=>laps(d,5,1)}}
      assert(e.getMessage.contains(diagnostic))
    }
  }
}
