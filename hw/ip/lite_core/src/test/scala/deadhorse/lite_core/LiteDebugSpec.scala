package deadhorse.lite_core
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class LiteDebugSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t32/lite-debug").toAbsolutePath
  }
  def high(b: Bool)=b.peek().litToBoolean
  val base=0x30000000L
  class Driver(d: LiteHart) {
    var cycles=0;var retired=Vector.empty[(Long,Long,Long)]
    d.reset_n.poke(false.B);d.start.poke(false.B);d.entry.poke(base.U);d.irq.poke(false.B)
    d.debug.get.request.poke(false.B);d.debug.get.allowEntry.poke(true.B);d.debug.get.stop.poke(false.B)
    d.bus.gnt.poke(false.B);d.bus.rvalid.poke(false.B);d.bus.err.poke(false.B);d.bus.rdata.poke(0.U)
    d.clk.step(3);d.reset_n.poke(true.B)
    def tick(n: Int=1): Unit=for(_<-0 until n) {
      d.clk.step();cycles+=1;assert(cycles<500,"LITE_DEBUG_DEADLINE")
      if(high(d.rvfi.valid)) retired :+= ((d.rvfi.pc_rdata.peek().litValue.toLong,
        d.rvfi.rd_addr.peek().litValue.toLong,d.rvfi.rd_wdata.peek().litValue.toLong))
    }
    def grant(addr: Long,write: Boolean=false,value: Long=0): Unit={
      while(!high(d.bus.req)) tick()
      def check(): Unit={
        assert(d.bus.bits.addr.peek().litValue==addr && high(d.bus.bits.we)==write,"LITE_DEBUG_ADDRESS")
        if(write) assert(d.bus.bits.wdata.peek().litValue==value,"LITE_DEBUG_DATA")
      }
      check();tick(3);check();d.bus.gnt.poke(true.B);tick();d.bus.gnt.poke(false.B)
    }
    def response(value: Long): Unit={
      tick(4);d.bus.rdata.poke(value.U);d.bus.rvalid.poke(true.B);tick();d.bus.rvalid.poke(false.B)
      tick(3)
    }
    def fetch(addr: Long,insn: Long): Unit={grant(addr);response(insn)}
  }
  def precise(d: LiteHart): Unit={
    val h=new Driver(d)
    d.start.poke(true.B);h.tick();d.start.poke(false.B)
    h.fetch(base,0x300000b7L) // lui x1,0x30000
    h.fetch(base+4,0x1000a283L) // lw x5,256(x1)
    h.grant(base+0x100)
    d.debug.get.request.poke(true.B);h.tick(7)
    assert(!high(d.debug.get.mode),"LITE_DEBUG_PRECISE_LOAD")
    h.response(41)
    while(!high(d.debug.get.mode)) h.tick()
    assert(!high(d.halted),"LITE_DEBUG_NORMAL_START_PRESERVED")
    assert(h.retired.last==(base+4,5L,41L),"LITE_DEBUG_LOAD_RETIREMENT")
    val count=h.retired.size
    d.debug.get.request.poke(false.B)
    h.fetch(0x10800,0x7b1023f3L) // csrr x7,dpc
    h.fetch(0x10804,0x1070a423L) // sw x7,264(x1)
    h.grant(base+0x108,true,base+8);h.response(0)
    h.fetch(0x10808,0x10500073L) // WFI is a NOP in debug
    assert(!high(d.sleeping),"LITE_DEBUG_WFI_NOP")
    h.fetch(0x1080c,0x7b200073L) // dret
    assert(!high(d.debug.get.mode),"LITE_DEBUG_DRET")
    assert(h.retired.size==count,"LITE_DEBUG_NO_APPLICATION_RETIREMENT")
    h.fetch(base+8,0x00128313L) // addi x6,x5,1
    assert(h.retired.last==(base+8,6L,42L),"LITE_DEBUG_RESUME_STATE")
  }
  test("halt waits for an in-flight load; DPC/resume state and debug WFI match contract") {
    simulateRaw(new LiteHart(withDebug=true))(precise)
  }
  test("actual register writeback fault fails the architectural bus oracle") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new LiteHart(corrupt=true,withDebug=true))(precise)
    }
    // The injected fault also changes the setup LUI, so the independent bus
    // address oracle rejects it before the pending-load/debug-entry sequence.
    assert(e.getMessage.contains("LITE_DEBUG_ADDRESS"))
  }
  test("debug-only entry preserves notStarted; illegal debug instruction uses exception vector") {
    simulateRaw(new LiteHart(withDebug=true)) {d=>
      val h=new Driver(d);d.debug.get.request.poke(true.B)
      while(!high(d.debug.get.mode)) h.tick()
      d.debug.get.request.poke(false.B)
      assert(high(d.halted),"LITE_DEBUG_NO_LOADER_START")
      h.fetch(0x10800,0) // illegal instruction
      h.grant(0x10810)
      assert(high(d.debug.get.mode) && high(d.halted) && h.retired.isEmpty,"LITE_DEBUG_EXCEPTION")
    }
  }
}
