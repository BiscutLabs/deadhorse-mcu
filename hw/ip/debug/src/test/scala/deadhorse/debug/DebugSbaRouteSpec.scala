package deadhorse.debug
import chisel3._
import chisel3.util._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import deadhorse.lib._
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Uses the same wire-level demultiplexer as the production SoC. */
class DebugSbaRouteFixture(wrongRoute: Boolean=false) extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val request=IO(Input(Bool()));val address=IO(Input(UInt(32.W)));val value=IO(Input(UInt(32.W)))
  val write=IO(Input(Bool()));val up=IO(Input(Bool()));val quiet=IO(Input(Bool()))
  val grant=IO(Output(Bool()));val valid=IO(Output(Bool()));val result=IO(Output(UInt(32.W)));val error=IO(Output(Bool()))
  val native=IO(Flipped(new LocalBus));val retained=IO(Flipped(new LocalBus))
  val d=Module(new DebugSba {override protected def route(v: Bool): Bool=if(wrongRoute) !v else v})
  d.clk:=clk;d.reset_n:=reset_n;d.req:=request;d.address:=address;d.value:=value;d.write:=write;d.mask:=15.U
  d.targetUp:=up;d.targetQuiet:=quiet;grant:=d.grant;valid:=d.valid;result:=d.result;error:=d.error
  DebugSbaRouting.connect(d.bus,d.retained,retained,native)
}

class DebugSbaRouteSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t32/sba-route-unit").toAbsolutePath
  }
  def exercise(fault: Boolean): Unit=simulateRaw(new DebugSbaRouteFixture(fault)) {d=>
    def high(b: Bool)=b.peek().litToBoolean
    def idlePorts(): Unit=Seq(d.native,d.retained).foreach {p=>
      p.gnt.poke(false.B);p.rvalid.poke(false.B);p.rdata.poke(0.U);p.err.poke(false.B)
    }
    d.reset_n.poke(false.B);d.request.poke(false.B);d.address.poke(0.U);d.value.poke(0.U)
    d.write.poke(false.B);d.up.poke(true.B);d.quiet.poke(true.B);idlePorts();d.clk.step(3);d.reset_n.poke(true.B)
    // Explicit map-boundary oracle, including misaligned addresses aligned by SBA.
    val cases=Seq((0x20000000L,false),(0x30000000L,true),(0x30000bffL,true),
      (0x30000c00L,false),(0x2fffffffL,false),(0x30000004L,true),(0x40010000L,false))
    val random=new scala.util.Random(3202);println("SBA route seed 3202")
    for(round<-0 until 4;((address,retained),index)<-cases.zipWithIndex) {
      idlePorts();val selected=if(retained)d.retained else d.native;val other=if(retained)d.native else d.retained
      val value=random.nextLong() & 0xffffffffL;val writing=round==1
      d.request.poke(true.B);d.address.poke(address.U);d.value.poke(value.U);d.write.poke(writing.B)
      var cycles=0;while(!high(d.grant)) {d.clk.step();cycles+=1;assert(cycles<16)}
      d.clk.step();d.request.poke(false.B);d.address.poke((address ^ 0x10000000L).U);d.value.poke(0.U)
      other.gnt.poke(true.B);other.rvalid.poke(true.B);other.rdata.poke(0xdeadbeefL.U);other.err.poke(true.B)
      for(_<-0 to random.nextInt(5)) {
        assert(high(selected.req) && !high(other.req),"wrong route")
        assert(selected.bits.addr.peek().litValue==(address & ~3L))
        assert(selected.bits.wdata.peek().litValue==value && selected.bits.origin.peek().litValue==2)
        assert(!high(d.valid));d.clk.step()
      }
      selected.gnt.poke(true.B);d.clk.step();selected.gnt.poke(false.B)
      assert(!high(selected.req) && !high(other.req) && !high(d.valid))
      if(round==2) {
        // Service reset cancels exactly once, then blocks new work until old responses drain.
        d.up.poke(false.B);d.quiet.poke(false.B);d.clk.step();assert(high(d.valid) && high(d.error))
        d.clk.step();d.up.poke(true.B);d.request.poke(true.B);selected.rvalid.poke(true.B)
        for(_<-0 until 4) {assert(!high(d.grant) && !high(d.valid));d.clk.step()}
        d.request.poke(false.B);idlePorts();d.quiet.poke(true.B);d.clk.step(2)
      } else if(round==3) {
        // POR destroys transaction ownership; a stale response cannot create a completion.
        d.reset_n.poke(false.B);d.clk.step(2);d.reset_n.poke(true.B);selected.rvalid.poke(true.B)
        for(_<-0 until 4) {assert(!high(d.valid) && !high(d.native.req) && !high(d.retained.req));d.clk.step()}
      } else {
        d.clk.step(3);assert(!high(d.valid))
        selected.rdata.poke(value.U);selected.rvalid.poke(true.B);selected.err.poke((index==4).B)
        d.clk.step();assert(high(d.valid) && high(d.error)==(index==4))
        assert(d.result.peek().litValue==(if(writing || index==4)0L else value))
        selected.rvalid.poke(false.B);d.clk.step();assert(!high(d.valid))
      }
      idlePorts();d.clk.step(2)
    }
  }
  test("SBA selects one registered destination and preserves payload, response and reset ownership") {exercise(false)}
  test("wrong destination control is detected") {
    val failure=intercept[org.scalatest.exceptions.TestFailedException] {exercise(true)}
    assert(failure.getMessage.contains("wrong route"))
  }
}
