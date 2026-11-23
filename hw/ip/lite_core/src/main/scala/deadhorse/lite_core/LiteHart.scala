package deadhorse.lite_core
import chisel3._
import deadhorse.lib.LocalBus

class LiteHart(origin: Int=0,corrupt: Boolean=false,withDebug: Boolean=false) extends RawModule {
  val debug=if(withDebug) Some(IO(new LiteDebugPort)) else None
  val debugIdle=if(withDebug) Some(IO(Output(Bool()))) else None
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val start=IO(Input(Bool()));val entry=IO(Input(UInt(32.W)));val irq=IO(Input(Bool()))
  val bus=IO(Flipped(new LocalBus));val halted=IO(Output(Bool()))
  val sleeping=IO(Output(Bool()));val clockHold=IO(Output(Bool()))
  val trace=IO(Output(new Retirement));val rvfi=IO(Output(new LiteRvfi));val interruptTaken=IO(Output(Bool()))
  val core=Module[LiteCore](if(corrupt) new LiteCore(withDebug) {
    override protected def writeback(value: UInt): UInt=value ^ 1.U
  } else new LiteCore(withDebug))
  debug.foreach(d=>core.debug.get<>d)
  val adapter=Module(new LiteBusAdapter(origin))
  core.clk:=clk;core.reset_n:=reset_n;core.start:=start;core.entry:=entry;core.irq:=irq
  adapter.clk:=clk;adapter.reset_n:=reset_n;adapter.request<>core.request;core.response<>adapter.response
  debugIdle.foreach(_:=core.debug.get.stopped && !adapter.busy)
  bus<>adapter.bus;halted:=core.halted;sleeping:=core.sleeping;clockHold:=core.clockHold
  trace:=core.trace;rvfi:=core.rvfi;interruptTaken:=core.interruptTaken
}
object EmitLiteHart extends App {
  require(args.length==1)
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(new LiteHart,Array("--target-dir",args(0)),
    Array("--disable-all-randomization","--strip-debug-info","--preserve-values=named",
      "--verification-flavor=immediate","--lower-to-core"))
}
