package deadhorse.top
import chisel3._
import chisel3.simulator.{ChiselSim,Randomization,Settings}
import chisel3.testing.HasTestingDirectory
import deadhorse.lib.LocalBus
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SocDmaMemorySpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t23/memory-simulation").toAbsolutePath
  }
  val settings=Settings.defaultRaw[SocLocalMemory].copy(randomization=Randomization.random.copy(memories=false))
  val base=SocTestFiles.description.region("performance_sram").base
  def high(b: Bool)=b.peek().litToBoolean
  def drive(p: LocalBus,a: BigInt,w: Boolean=false,v: BigInt=0,be: Int=15,owner: Int=1): Unit={
    p.req.poke(true.B);p.bits.addr.poke(a.U);p.bits.we.poke(w.B);p.bits.wdata.poke(v.U)
    p.bits.be.poke(be.U);p.bits.origin.poke(owner.U)
  }
  def init(d: SocLocalMemory): Unit={
    (Seq(d.instruction,d.data)++d.dma.toSeq).foreach {p=>drive(p,0);p.req.poke(false.B)}
    d.peripheral.gnt.poke(false.B);d.peripheral.rvalid.poke(false.B);d.peripheral.rdata.poke(0.U);d.peripheral.err.poke(false.B)
    d.serviceReset_n.poke(false.B);d.clientReset_n.poke(false.B);d.clk.step(3)
    d.serviceReset_n.poke(true.B);d.clientReset_n.poke(true.B);d.clk.step(4)
  }
  for(latency<-Seq(1,3)) {
    test(s"idle DMA preserves CPU grant/response trace at latency $latency") {
      def trace(enabled: Boolean): Vector[(Boolean,Boolean,Boolean,Boolean,BigInt,BigInt)]={
        var result=Vector.empty[(Boolean,Boolean,Boolean,Boolean,BigInt,BigInt)]
        simulateRaw(new SocLocalMemory(SocTestFiles.description,SocTestFiles.memoryRom,
          readLatency=latency,dmaEnabled=enabled),settings=settings) {d=>
          init(d);var pending=false;var index=0
          for(cycle<-0 until 180) {
            drive(d.instruction,(cycle%32)*4)
            if(!pending && cycle%7==0) {drive(d.data,((index+3)%32)*4);index+=1;pending=true}
            val g=high(d.data.gnt) && high(d.data.req)
            result:+=((high(d.instruction.gnt),high(d.data.gnt),high(d.instruction.rvalid),high(d.data.rvalid),
              if(high(d.instruction.rvalid)) d.instruction.rdata.peek().litValue else BigInt(0),
              if(high(d.data.rvalid)) d.data.rdata.peek().litValue else BigInt(0)))
            val done=high(d.data.rvalid);d.clk.step();if(g) d.data.req.poke(false.B);if(done) pending=false
          }
        };result
      }
      assert(trace(false)==trace(true),"IDLE_DMA_CPU_TRACE")
    }
    test(s"DMA memory arbitration, lane ownership and core-reset retention at latency $latency") {
      simulateRaw(new SocLocalMemory(SocTestFiles.description,SocTestFiles.memoryRom,
        readLatency=latency,dmaEnabled=true),settings=settings) {d=>
        init(d);val m=d.dma.get;var cycle=0;var fetches=0
        val expected=scala.collection.mutable.Queue.empty[(Int,BigInt)]
        def tick(): Unit={
          if(high(d.instruction.rvalid)) {
            assert(expected.nonEmpty && expected.front._1==cycle,"DMA_FETCH_RESPONSE_TIME")
            assert(d.instruction.rdata.peek().litValue==expected.dequeue()._2,"DMA_FETCH_DATA");fetches+=1
          }
          if(high(d.instruction.req) && high(d.instruction.gnt))
            expected.enqueue((cycle+latency,SocTestFiles.romWord((d.instruction.bits.addr.peek().litValue/4).toInt)))
          d.clk.step();cycle+=1
        }
        def access(port: LocalBus,a: BigInt,w: Boolean=false,v: BigInt=0,be: Int=15,owner: Int=1): (BigInt,Boolean)={
          drive(port,a,w,v,be,owner);var n=0
          while(!high(port.gnt)) {tick();n+=1;assert(n<8,"DMA_ARBITRATION_BOUND")}
          tick();port.req.poke(false.B)
          for(_<-1 until latency) {assert(!high(port.rvalid));tick()}
          assert(high(port.rvalid));val r=(port.rdata.peek().litValue,high(port.err));tick();r
        }
        drive(d.instruction,28)
        assert(access(m,base,true,BigInt("11223344",16))==(BigInt(0),false))
        assert(access(d.data,base)==(BigInt("11223344",16),false))
        assert(access(m,base,true,BigInt("ab0000",16),4)==(BigInt(0),false))
        assert(access(d.data,base)==(BigInt("11ab3344",16),false))
        for((a,o)<-Seq((base,0),(BigInt(0),1),(BigInt(0x40010000L),1),(base+1,1)))
          assert(access(m,a,owner=o)._2,"DMA_PRIVATE_RAM_ONLY")
        for(i<-0 until 16) {assert(!access(m,base+4*i,true,i+100)._2);assert(access(d.data,base+4*i)==(BigInt(i+100),false))}
        assert(fetches>32)
        d.instruction.req.poke(false.B);for(_<-0 until latency+1) tick()
        drive(m,base+4,true,0x55667788);while(!high(m.gnt)) tick()
        tick();m.req.poke(false.B);d.clientReset_n.poke(false.B)
        for(_<-1 until latency) tick()
        assert(high(m.rvalid) && !high(m.err),"DMA_CORE_RESET_REPLY");tick()
        assert(access(m,base+4)==(BigInt(0x55667788),false),"DMA_CORE_RESET_MEMORY")
        d.serviceReset_n.poke(false.B);assert(!high(m.rvalid));d.clk.step(2)
      }
    }
  }
}
