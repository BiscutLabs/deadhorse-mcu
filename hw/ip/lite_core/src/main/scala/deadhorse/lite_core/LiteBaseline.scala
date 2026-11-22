package deadhorse.lite_core
import chisel3._
import deadhorse.lib.LocalBus

/** Faithful RV32E baseline plus the registered bus boundary; not the final hart. */
class LiteBaseline(corrupt: Boolean=false) extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val bus=IO(Flipped(new LocalBus));val halted=IO(Output(Bool()))
  val trace=IO(Output(new Retirement));val traceEvent=IO(Output(Bool()))
  val adapter=Module[LiteBusAdapter](if(corrupt) new LiteBusAdapter {
    override protected def returned(data: UInt): UInt=data ^ 1.U
  } else new LiteBusAdapter)
  adapter.clk:=clk;adapter.reset_n:=reset_n;bus<>adapter.bus;halted:=adapter.halted
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val core=Module(new ClockedCore)
    adapter.request<>core.request;core.response<>adapter.response
    trace:=core.trace;traceEvent:=core.traceEvent
  }
}
object EmitLiteBaseline extends App {
  require(args.length==1)
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(new LiteBaseline,Array("--target-dir",args(0)),
    Array("--disable-all-randomization","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
