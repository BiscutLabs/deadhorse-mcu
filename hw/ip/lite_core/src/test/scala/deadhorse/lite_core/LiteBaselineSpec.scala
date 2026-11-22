package deadhorse.lite_core
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class LiteBaselineSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t25/baseline-simulation").toAbsolutePath
  }
  def high(v: Bool)=v.peek().litToBoolean
  def oracle(d: LiteBaseline,expected: Reference.Result,seed: Int): Unit={
    d.reset_n.poke(false.B);d.bus.gnt.poke(false.B);d.bus.rvalid.poke(false.B)
    d.bus.rdata.poke(0.U);d.bus.err.poke(false.B);d.clk.step(3);d.reset_n.poke(true.B)
    var retired=0;var cycles=0;val random=new scala.util.Random(seed)
    def tick(n: Int=1): Unit=for(_<-0 until n) {
      d.clk.step();cycles+=1;assert(cycles<30000,"LITE_DEADLINE")
      if(high(d.traceEvent)) {
        assert(retired<expected.traces.size,"LITE_EXTRA_RETIREMENT")
        val t=expected.traces(retired);val a=d.trace
        assert(a.pc.peek().litValue==t.pc && a.instruction.peek().litValue==t.instruction &&
          a.rd.peek().litValue==t.rd && a.data.peek().litValue==t.data &&
          high(a.writeRegister)==(t.rd!=0 && !t.trap) && high(a.trap)==t.trap &&
          a.cause.peek().litValue==t.cause,"LITE_TRACE_ORACLE")
        retired+=1
      }
    }
    for(a<-expected.accesses if a.op!=3) {
      while(!high(d.bus.req)) tick()
      def check(): Unit={
        assert(high(d.bus.req) && d.bus.bits.addr.peek().litValue==(a.address & ~3L) &&
          d.bus.bits.wdata.peek().litValue==a.data && d.bus.bits.be.peek().litValue==a.mask &&
          high(d.bus.bits.we)==(a.op==2) && d.bus.bits.origin.peek().litValue==0,"LITE_BUS_ORACLE")
      }
      check();for(_<-0 until random.nextInt(5)) {tick();check()}
      d.bus.gnt.poke(true.B);tick();d.bus.gnt.poke(false.B)
      assert(!high(d.bus.req),"LITE_DUPLICATE_OFFER")
      tick(random.nextInt(7))
      d.bus.rdata.poke(a.response.U);d.bus.err.poke(a.error.B);d.bus.rvalid.poke(true.B)
      tick();d.bus.rvalid.poke(false.B)
    }
    while(!high(d.halted)) {assert(!high(d.bus.req),"LITE_HALT_WENT_TO_BUS");tick()}
    tick(5);assert(retired==expected.traces.size && !high(d.bus.req),"LITE_RETIREMENT_COUNT")
  }
  test("pinned RV32E baseline matches independent ISA/bus oracle with stalls; seeds1,19") {
    simulateRaw(new LiteBaseline) {d=>
      for(p<-Seq(CorePrograms.arithmetic,CorePrograms.memoryAndControl,CorePrograms.predicates);seed<-Seq(1,19))
        oracle(d,Reference.run(p),seed)
    }
  }
  test("illegal registers/encodings, access faults and alignment preserve exception causes") {
    import Assembly._
    val programs=Seq(Seq(0L),Seq(i(0x13,16,0,0,1)),Seq(i(0x13,1,0,16,1)),Seq(r(1,0,0,16)),
      Seq(r(1,0,0,0,1)),Seq(0x100fL),Seq(0x73L),Seq(jal(1,2)),Seq(i(0x03,1,2,0,1)),
      Seq(store(0,1,1,1)),Seq(i(0x03,1,2,0,1024)),Seq(store(0,1,1024,2)))
    simulateRaw(new LiteBaseline) {d=>
      for(p<-programs) oracle(d,Reference.run(p,denied=Set(1024L)),19)
      oracle(d,Reference.run(Seq(breakpoint),denied=Set(0L)),1)
    }
  }
  test("actual returned-data corruption is rejected by the unchanged oracle") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new LiteBaseline(corrupt=true))(d=>oracle(d,Reference.run(CorePrograms.known),1))
    };assert(e.getMessage.contains("LITE_TRACE_ORACLE"))
  }
}
