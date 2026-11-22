package deadhorse.lite_core
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Production hart, independently predicted bus transfers and retirement. */
class LiteHartSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t25/hart-simulation").toAbsolutePath
  }
  def high(v: Bool)=v.peek().litToBoolean
  def oracle(d: LiteHart,expected: Reference.Result,seed: Int): Unit={
    d.reset_n.poke(false.B);d.start.poke(false.B);d.entry.poke(0.U);d.irq.poke(false.B)
    d.bus.gnt.poke(false.B);d.bus.rvalid.poke(false.B);d.bus.rdata.poke(0.U);d.bus.err.poke(false.B)
    d.clk.step(3);d.reset_n.poke(true.B);d.clk.step(5)
    assert(high(d.halted) && !high(d.bus.req),"HART_FETCH_BEFORE_START")
    d.start.poke(true.B);d.clk.step();d.start.poke(false.B)
    var retired=0;var cycles=0;val random=new scala.util.Random(seed)
    var lastAccess=Reference.Access(0,0,0,0,0)
    def tick(n: Int=1): Unit=for(_<-0 until n) {
      d.clk.step();cycles+=1;assert(cycles<30000,"HART_DEADLINE")
      if(high(d.rvfi.valid)) {
        assert(retired<expected.traces.size,"HART_EXTRA_RETIREMENT")
        val t=expected.traces(retired);val a=d.trace;val r=d.rvfi
        assert(high(a.valid) && a.pc.peek().litValue==t.pc && a.instruction.peek().litValue==t.instruction &&
          a.rd.peek().litValue==t.rd && a.data.peek().litValue==t.data && high(a.trap)==t.trap &&
          a.cause.peek().litValue==t.cause,"HART_TRACE_ORACLE")
        assert(r.order.peek().litValue==retired && r.pc_rdata.peek().litValue==t.pc &&
          r.insn.peek().litValue==t.instruction && r.rd_addr.peek().litValue==t.rd &&
          r.rd_wdata.peek().litValue==(if(t.rd==0) 0L else t.data) && high(r.trap)==t.trap,"HART_RVFI_ORACLE")
        if(lastAccess.op==1 || lastAccess.op==2) {
          assert(r.mem_addr.peek().litValue==(lastAccess.address & ~3L) &&
            r.mem_rmask.peek().litValue==(if(lastAccess.op==1) lastAccess.mask else 0) &&
            r.mem_wmask.peek().litValue==(if(lastAccess.op==2) lastAccess.mask else 0),"HART_RVFI_LANES")
          if(lastAccess.op==1) assert(r.mem_rdata.peek().litValue==lastAccess.response,"HART_RVFI_READ")
          else assert(r.mem_wdata.peek().litValue==lastAccess.data,"HART_RVFI_WRITE")
        }
        retired+=1
      }
    }
    for(a<-expected.accesses if a.op!=3) {
      while(!high(d.bus.req)) tick()
      def check(): Unit=assert(high(d.bus.req) && d.bus.bits.addr.peek().litValue==(a.address & ~3L) &&
        d.bus.bits.wdata.peek().litValue==a.data && d.bus.bits.be.peek().litValue==a.mask &&
        high(d.bus.bits.we)==(a.op==2) && d.bus.bits.origin.peek().litValue==0,"HART_BUS_ORACLE")
      check();for(_<-0 until random.nextInt(5)) {tick();check()}
      d.bus.gnt.poke(true.B);tick();d.bus.gnt.poke(false.B)
      assert(!high(d.bus.req),"HART_DUPLICATE_OFFER");tick(random.nextInt(7))
      lastAccess=a;d.bus.rdata.poke(a.response.U);d.bus.err.poke(a.error.B);d.bus.rvalid.poke(true.B)
      tick();d.bus.rvalid.poke(false.B)
    }
    while(retired<expected.traces.size) tick()
    // The production extension traps rather than emitting legacy terminal Halt.
    assert(!high(d.halted) && !high(d.sleeping),"HART_TRAP_IS_NOT_HALT")
    while(!high(d.bus.req)) {d.clk.step();cycles+=1;assert(cycles<30000)}
    assert(d.bus.bits.addr.peek().litValue==0 && !high(d.bus.bits.we),"HART_TRAP_VECTOR")
    // Common service reset cancels an offered transfer without a response.
    d.reset_n.poke(false.B);assert(!high(d.bus.req) && high(d.halted),"HART_ASYNC_CANCEL")
    d.clk.step();d.reset_n.poke(true.B);d.clk.step(5)
    assert(!high(d.bus.req) && high(d.halted),"HART_RESET_REPLAY")
  }
  test("production RV32E matches independent oracle under stalls and resets; seeds1,19") {
    simulateRaw(new LiteHart) {d=>
      for(p<-Seq(CorePrograms.arithmetic,CorePrograms.memoryAndControl,CorePrograms.predicates);seed<-Seq(1,19))
        oracle(d,Reference.run(p),seed)
    }
  }
  test("physical RVFI lanes cover every byte offset and halfword offset two") {
    import Assembly._
    val p=Seq(i(0x13,15,0,0,1024),i(0x13,1,0,0,-67)) ++
      (0 until 4).flatMap(x=>Seq(store(15,1,x,0),i(0x03,2,0,15,x),i(0x03,3,4,15,x))) ++
      Seq(store(15,1,2,1),i(0x03,4,1,15,2),i(0x03,5,5,15,2),breakpoint)
    simulateRaw(new LiteHart)(d=>oracle(d,Reference.run(p),19))
  }
  test("production hart preserves illegal, alignment and bus fault causes") {
    import Assembly._
    val programs=Seq(Seq(0L),Seq(i(0x13,16,0,0,1)),Seq(i(0x13,1,0,16,1)),Seq(r(1,0,0,16)),
      Seq(r(1,0,0,0,1)),Seq(0x100fL),Seq(0x73L),Seq(jal(1,2)),Seq(i(0x03,1,2,0,1)),
      Seq(store(0,1,1,1)),Seq(i(0x03,1,2,0,1024)),Seq(store(0,1,1024,2)))
    simulateRaw(new LiteHart) {d=>
      for(p<-programs) oracle(d,Reference.run(p,denied=Set(1024L)),19)
      oracle(d,Reference.run(Seq(breakpoint),denied=Set(0L)),1)
    }
  }
  test("actual register writeback corruption fails the architectural oracle") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new LiteHart(corrupt=true))(d=>oracle(d,Reference.run(CorePrograms.known),1))
    };assert(e.getMessage.contains("HART_RVFI_ORACLE") || e.getMessage.contains("HART_TRACE_ORACLE"))
  }
}
