package deadhorse.top

import chisel3._
import deadhorse.bus.{BusFabric,BusRegion}
import deadhorse.lib._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Actual production-depth nested fabrics, with an externally delayed target. */
class SocNestedBench extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val bus=IO(new LocalBus);val target=IO(Flipped(new LocalBus));val quiet=IO(Output(Bool()))
  val parent=Module(new BusFabric(1,Seq(BusRegion(BigInt("40000000",16),256))))
  val child=Module(new BusFabric(1,Seq(BusRegion(BigInt("40000000",16),256))))
  val drain=Module(new SocNestedDrain)
  for(f<-Seq(parent,child)) {
    f.clk:=clk;f.reset_n:=reset_n;f.allow(0):=true.B;f.admit(0):=true.B
  }
  parent.master(0)<>bus;child.master(0)<>parent.target(0);target<>child.target(0)
  child.quiescent(0):=false.B;parent.quiescent(0):=drain.quiescent
  drain.clk:=clk;drain.reset_n:=reset_n
  drain.request:=child.master(0).req;drain.grant:=child.master(0).gnt;drain.response:=child.master(0).rvalid
  drain.waiting:=child.waiting(0);drain.isolated:=child.isolated(0)
  drain.targetRequest:=target.req;drain.targetResponse:=target.rvalid;quiet:=drain.quiescent
}

class SocNestedSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t20/i1/nested-simulation").toAbsolutePath
  }
  def high(pin: Bool): Boolean=pin.peek().litToBoolean
  test("late endpoint completion cannot acknowledge quiet or contaminate fresh traffic after nested watchdogs") {
    simulateRaw(new SocNestedBench) { d =>
      d.reset_n.poke(false.B);d.bus.req.poke(false.B);d.bus.bits.poke(0.U.asTypeOf(d.bus.bits))
      d.target.gnt.poke(false.B);d.target.rvalid.poke(false.B);d.target.rdata.poke(0.U);d.target.err.poke(false.B)
      d.clk.step(3);d.reset_n.poke(true.B);d.clk.step(3)
      def offer(): Unit = {
        d.bus.req.poke(true.B);d.bus.bits.addr.poke(0x40000000L.U);d.bus.bits.origin.poke(1.U)
        var n=0;while(!high(d.bus.gnt)) {d.clk.step();n+=1;assert(n<8)}
        d.clk.step();d.bus.req.poke(false.B)
        n=0;while(!high(d.target.req)) {d.clk.step();n+=1;assert(n<16)}
        d.target.gnt.poke(true.B);d.clk.step();d.target.gnt.poke(false.B)
      }
      offer()
      var errors=0
      for(_<-0 until 145) {
        assert(!high(d.quiet),"I1_EARLY_NESTED_DRAIN")
        if(high(d.bus.rvalid)) {assert(high(d.bus.err));errors+=1}
        d.clk.step()
      }
      assert(errors==1,"I1_NESTED_TIMEOUT_EXACTLY_ONCE")
      d.target.rdata.poke(0xdeadbeefL.U);d.target.rvalid.poke(true.B)
      d.clk.step();d.target.rvalid.poke(false.B)
      for(_<-0 until 8) {assert(!high(d.bus.rvalid),"I1_LATE_RESPONSE_ESCAPED");d.clk.step()}
      assert(high(d.quiet),"I1_NESTED_DRAIN_STUCK")
      offer();d.target.rdata.poke(0x13579bdfL.U);d.target.rvalid.poke(true.B)
      d.clk.step();d.target.rvalid.poke(false.B)
      var n=0;while(!high(d.bus.rvalid)) {d.clk.step();n+=1;assert(n<16)}
      assert(!high(d.bus.err) && d.bus.rdata.peek().litValue==0x13579bdfL,"I1_FRESH_REPLY")
      d.clk.step(8);assert(!high(d.bus.rvalid) && high(d.quiet))
    }
  }
}
