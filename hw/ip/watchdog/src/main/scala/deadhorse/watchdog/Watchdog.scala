package deadhorse.watchdog
import chisel3._
import chisel3.util._
import deadhorse.lib._

class Watchdog(json: String,base: BigInt=0,owner: Int=1,withPause: Boolean=false) extends RawModule {
  val pause=if(withPause) Some(IO(Input(Bool()))) else None
  val clk=IO(Input(Clock()));val por_n=IO(Input(Bool()));val reset_n=IO(Input(Bool()))
  val bus=IO(new LocalBus)
  val active=IO(Output(Bool()));val warn=IO(Output(Bool()));val resetHold=IO(Output(Bool()))
  val cause=IO(Output(Bool()));val crashes=IO(Output(UInt(32.W)))
  protected def permitted(origin: UInt): Bool=origin===owner.U
  val regs=Module(new RegBlock(json));regs.clk:=clk;regs.rst_n:=reset_n
  val adapter=Module(new BusRegAdapter(8,base,0));adapter.clk:=clk;adapter.reset_n:=reset_n
  adapter.bus.req:=bus.req;adapter.bus.bits:=bus.bits
  adapter.bus.bits.origin:=Mux(permitted(bus.bits.origin),0.U,7.U)
  bus.gnt:=adapter.bus.gnt;bus.rvalid:=adapter.bus.rvalid;bus.rdata:=adapter.bus.rdata;bus.err:=adapter.bus.err
  regs.bus<>adapter.registers
  val channel=Module(new WatchdogChannel(withPause));channel.clk:=clk;channel.por_n:=por_n;channel.reset_n:=reset_n
  channel.pause.foreach(_:=pause.get)
  channel.period:=regs.hw("period_ticks_q");channel.window:=regs.hw("window_ticks_q")
  channel.warning:=regs.hw("warning_ticks_q")
  val startWrite=regs.hw("start_key_we").asBool;val feedWrite=regs.hw("feed_key_we").asBool
  val startKey=regs.hw("start_key_wdata")==="h57445354".U
  val feedKey=regs.hw("feed_key_wdata")==="h57444644".U
  channel.start:=startWrite && startKey;channel.feed:=feedWrite && feedKey
  regs.hw("events_error_set"):=channel.error || startWrite && !startKey || feedWrite && !feedKey
  regs.hw("status_flags_d"):=Cat(channel.cause,channel.resetHold,channel.warn,channel.active)
  regs.hw("remaining_ticks_d"):=channel.remaining;regs.hw("crashes_count_d"):=channel.crashes
  active:=channel.active;warn:=channel.warn;resetHold:=channel.resetHold
  cause:=channel.cause;crashes:=channel.crashes
}
object EmitWatchdog extends App {
  require(args.length==2)
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(new Watchdog(args(0)),Array("--target-dir",args(1)),
    Array("--disable-all-randomization","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
