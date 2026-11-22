package deadhorse.top
import chisel3._
import chisel3.simulator.{ChiselSim,Randomization,Settings}
import chisel3.testing.HasTestingDirectory
import deadhorse.lib.LocalBus
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SocXipMemorySpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t30/memory-simulation").toAbsolutePath
  }
  val settings=Settings.defaultRaw[SocLocalMemory].copy(randomization=Randomization.random.copy(memories=false))
  def high(b: Bool)=b.peek().litToBoolean
  def request(b: LocalBus,a: Long,w: Boolean=false,v: Long=0,origin: Int=1): Unit={
    b.req.poke(true.B);b.bits.addr.poke(a.U);b.bits.we.poke(w.B);b.bits.wdata.poke(v.U)
    b.bits.be.poke(15.U);b.bits.origin.poke(origin.U)
  }
  def reset(d: SocLocalMemory): Unit={
    d.serviceReset_n.poke(false.B);d.clientReset_n.poke(false.B)
    for(b<-Seq(d.instruction,d.data,d.dma.get)) {b.req.poke(false.B);b.bits.poke(0.U.asTypeOf(b.bits))}
    for(b<-Seq(d.peripheral,d.xip.get)) {b.gnt.poke(false.B);b.rvalid.poke(false.B);b.rdata.poke(0.U);b.err.poke(false.B)}
    d.clk.step(3);d.serviceReset_n.poke(true.B);d.clientReset_n.poke(true.B);d.clk.step(4)
    assert(high(d.epochReady))
  }
  def accept(d: SocLocalMemory,b: LocalBus): Unit={
    var n=0;while(!high(b.gnt)) {d.clk.step();n+=1;assert(n<16)}
    d.clk.step();b.req.poke(false.B)
  }
  def response(d: SocLocalMemory,v: Long): Unit={
    val x=d.xip.get
    x.rdata.poke(v.U);x.rvalid.poke(true.B);d.clk.step();x.rvalid.poke(false.B)
  }
  def drainExercise(d: SocLocalMemory,dataSide: Boolean=false,latency: Int=1): Unit={
    val b=if(dataSide)d.data else d.instruction
    for(stage<-0 to 3) {
      reset(d);val x=d.xip.get
      request(b,0x10000020L);accept(d,b)
      assert(high(x.req) && !high(b.rvalid))
      if(stage>0) {x.gnt.poke(true.B);d.clk.step();x.gnt.poke(false.B)}
      if(stage==2) {x.rvalid.poke(true.B);x.rdata.poke(0x12345678.U)}
      if(stage==3) response(d,0x12345678L)
      // Pulse entirely between sample edges; remembered reset must fence the old reply.
      d.clientReset_n.poke(false.B);assert(!high(d.epochReady) && !high(b.rvalid))
      d.clientReset_n.poke(true.B)
      if(stage==0) {x.gnt.poke(true.B);d.clk.step();x.gnt.poke(false.B)}
      if(stage<2) {d.clk.step(2);assert(!high(d.epochReady));response(d,0x12345678L)}
      if(stage==2) {d.clk.step();x.rvalid.poke(false.B)}
      for(_<-0 until 5) {assert(!high(b.rvalid),"XIP_ORPHAN_REPLY");d.clk.step()}
      assert(high(d.epochReady),"XIP_EPOCH_DRAIN")
      request(b,0);accept(d,b);if(latency>1)d.clk.step(latency-1)
      assert(high(b.rvalid) && b.rdata.peek().litValue==SocTestFiles.romWord(0))
    }
  }
  for(latency<-Seq(1,3);dataSide<-Seq(false,true)) test(s"client reset drains orphan XIP: latency=$latency data=$dataSide") {
    simulateRaw(new SocLocalMemory(SocTestFiles.description,SocTestFiles.memoryRom,readLatency=latency,dmaEnabled=true,xipEnabled=true),settings=settings)(d=>drainExercise(d,dataSide,latency))
  }
  test("bypassing the reset fence is rejected") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new SocLocalMemory(SocTestFiles.description,SocTestFiles.memoryRom,dmaEnabled=true,xipEnabled=true) {
        override protected def xipResponseAllowed(ready: Bool): Bool=true.B
      },settings=settings)(d=>drainExercise(d))
    };assert(e.getMessage.contains("XIP_ORPHAN_REPLY"))
  }
  test("local data and DMA continue during instruction XIP, ordered fetch and denied DMA") {
    simulateRaw(new SocLocalMemory(SocTestFiles.description,SocTestFiles.memoryRom,dmaEnabled=true,xipEnabled=true),settings=settings) {d=>
      reset(d);val x=d.xip.get
      // Preserve consecutive local instruction replies before transitioning to flash.
      for(i<-0 until 8) {request(d.instruction,i*4);assert(high(d.instruction.gnt));d.clk.step()
        assert(high(d.instruction.rvalid) && d.instruction.rdata.peek().litValue==SocTestFiles.romWord(i))}
      request(d.instruction,0x10000000L);accept(d,d.instruction)
      x.gnt.poke(true.B);d.clk.step();x.gnt.poke(false.B)
      request(d.data,0x20000000L,true,0x55667788L);accept(d,d.data);assert(high(d.data.rvalid) && !high(d.data.err));d.clk.step()
      request(d.dma.get,0x20000004L,true,0x11223344L);accept(d,d.dma.get);assert(high(d.dma.get.rvalid) && !high(d.dma.get.err));d.clk.step()
      request(d.data,0x20000004L);accept(d,d.data);assert(high(d.data.rvalid) && d.data.rdata.peek().litValue==0x11223344L);d.clk.step()
      request(d.instruction,0);assert(!high(d.instruction.gnt),"XIP_FETCH_ORDER")
      response(d,0xa1b2c3d4L);assert(high(d.instruction.rvalid) && d.instruction.rdata.peek().litValue==0xa1b2c3d4L)
      accept(d,d.instruction);assert(high(d.instruction.rvalid) && d.instruction.rdata.peek().litValue==SocTestFiles.romWord(0));d.clk.step()
      request(d.dma.get,0x10000000L);accept(d,d.dma.get);assert(high(d.dma.get.rvalid) && high(d.dma.get.err) && !high(x.req))
    }
  }
  test("restart waits for both native fetch and MMIO; neither orphan is returned") {
    simulateRaw(new SocLocalMemory(SocTestFiles.description,SocTestFiles.memoryRom,dmaEnabled=true,xipEnabled=true),settings=settings) {d=>
      reset(d);val x=d.xip.get;val p=d.peripheral
      request(d.data,0x40010000L);accept(d,d.data);p.gnt.poke(true.B);d.clk.step();p.gnt.poke(false.B)
      request(d.instruction,0x10000000L);accept(d,d.instruction);x.gnt.poke(true.B);d.clk.step();x.gnt.poke(false.B)
      d.clientReset_n.poke(false.B);assert(!high(d.epochReady));d.clientReset_n.poke(true.B)
      response(d,0x12345678L);d.clk.step(3)
      assert(!high(d.epochReady) && !high(d.instruction.rvalid) && !high(d.data.rvalid))
      p.rvalid.poke(true.B);p.rdata.poke(0x87654321L.U);d.clk.step();p.rvalid.poke(false.B)
      for(_<-0 until 5) {assert(!high(d.data.rvalid) && !high(d.instruction.rvalid));d.clk.step()}
      assert(high(d.epochReady))
    }
  }
  test("native instruction grant waits for every earlier three-stage local reply") {
    simulateRaw(new SocLocalMemory(SocTestFiles.description,SocTestFiles.memoryRom,readLatency=3,dmaEnabled=true,xipEnabled=true),settings=settings) {d=>
      reset(d);val x=d.xip.get
      for(i<-0 until 3) {request(d.instruction,i*4);assert(high(d.instruction.gnt));d.clk.step()}
      request(d.instruction,0x10000000L)
      for(i<-0 until 3) {
        assert(!high(d.instruction.gnt) && !high(x.req),"XIP_PRIOR_LOCAL_DRAIN")
        assert(high(d.instruction.rvalid) && d.instruction.rdata.peek().litValue==SocTestFiles.romWord(i))
        d.clk.step()
      }
      assert(high(d.instruction.gnt) && !high(d.instruction.rvalid))
      accept(d,d.instruction);assert(high(x.req))
      x.gnt.poke(true.B);d.clk.step();x.gnt.poke(false.B)
      response(d,0x12345678L)
      assert(high(d.instruction.rvalid) && d.instruction.rdata.peek().litValue==0x12345678L)
    }
  }
  test("data native reads coexist with ordered pipelined local fetch and propagate errors") {
    simulateRaw(new SocLocalMemory(SocTestFiles.description,SocTestFiles.memoryRom,readLatency=3,dmaEnabled=true,xipEnabled=true),settings=settings) {d=>
      reset(d);val x=d.xip.get
      request(d.data,0x10000000L);accept(d,d.data);x.gnt.poke(true.B);d.clk.step();x.gnt.poke(false.B)
      for(i<-0 until 8) {
        request(d.instruction,i*4);assert(high(d.instruction.gnt));d.clk.step()
        if(i>=2)assert(high(d.instruction.rvalid) && d.instruction.rdata.peek().litValue==SocTestFiles.romWord(i-2))
      }
      d.instruction.req.poke(false.B)
      response(d,0x76543210L)
      assert(high(d.data.rvalid) && !high(d.data.err) && d.data.rdata.peek().litValue==0x76543210L)
      assert(high(d.instruction.rvalid) && d.instruction.rdata.peek().litValue==SocTestFiles.romWord(6))
      d.clk.step(3)
      request(d.data,0x10000004L);accept(d,d.data);x.gnt.poke(true.B);d.clk.step();x.gnt.poke(false.B)
      x.err.poke(true.B);response(d,0xffffffffL)
      assert(high(d.data.rvalid) && high(d.data.err) && d.data.rdata.peek().litValue==0)
      // Whole service reset cancels accepted work, unlike the client-only reset.
      x.err.poke(false.B);d.clk.step(3)
      request(d.data,0x10000008L);accept(d,d.data)
      d.serviceReset_n.poke(false.B);assert(!high(x.req) && !high(d.data.rvalid) && !high(d.epochReady))
      d.clk.step(3);d.serviceReset_n.poke(true.B);d.clk.step(5);assert(high(d.epochReady))
    }
  }
}
