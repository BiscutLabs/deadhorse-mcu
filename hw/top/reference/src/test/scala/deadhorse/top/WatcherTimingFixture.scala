package deadhorse.top

import chisel3._
import deadhorse.bus.{BusFabric, BusRegion}
import deadhorse.lib.LocalBus
import deadhorse.lite_core.{LiteHart, Retirement}

/** PLAN05 Phase1 measurement only. Reuses the production lite instruction/data
  * route and registered fabric, with no other-master contention. The external
  * independent memory/radio oracle is deliberately optimistic; this is not a
  * replacement production top or a claim of integrated peripheral acceptance.
  */
class WatcherTimingFixture extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val start=IO(Input(Bool()));val entry=IO(Input(UInt(32.W)));val irq=IO(Input(Bool()))
  val bus=IO(Flipped(new LocalBus));val sleeping=IO(Output(Bool()))
  val trace=IO(Output(new Retirement))
  val hart=Module(new LiteHart(withDebug=true))
  hart.clk:=clk;hart.reset_n:=reset_n;hart.start:=start;hart.entry:=entry;hart.irq:=irq
  hart.debug.get.request:=false.B;hart.debug.get.allowEntry:=false.B;hart.debug.get.stop:=false.B
  sleeping:=hart.sleeping;trace:=hart.trace
  val route=Module(new SocDebugRoute)
  route.clk:=clk;route.reset_n:=reset_n;route.bus<>hart.bus
  route.debug.gnt:=false.B;route.debug.rvalid:=false.B;route.debug.rdata:=0.U;route.debug.err:=true.B
  val fabric=Module(new BusFabric(2,Seq(BusRegion(0,BigInt(1)<<32))))
  fabric.clk:=clk;fabric.reset_n:=reset_n;fabric.master(0)<>route.ordinary
  fabric.master(1).req:=false.B;fabric.master(1).bits:=0.U.asTypeOf(fabric.master(1).bits)
  fabric.allow.foreach(_:=true.B);fabric.admit.foreach(_:=true.B)
  fabric.quiescent.foreach(_:=false.B);bus<>fabric.target(0)
}

object EmitWatcherTimingFixture extends App {
  require(args.length==1)
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(new WatcherTimingFixture,
    Array("--target-dir",args(0)),Array("--disable-all-randomization",
      "--strip-debug-info","--preserve-values=named","--verification-flavor=immediate","--lower-to-core"))
}
