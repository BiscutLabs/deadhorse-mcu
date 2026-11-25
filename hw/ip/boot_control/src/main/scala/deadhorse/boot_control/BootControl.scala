package deadhorse.boot_control
import chisel3._
import chisel3.util._
import deadhorse.lib._

class BootControl(json: String,base: BigInt=0,owner: Int=1) extends RawModule {
  val clk=IO(Input(Clock()));val epochReset_n=IO(Input(Bool()));val reset_n=IO(Input(Bool()))
  val quiet=IO(Input(Bool()));val debugOwned=IO(Input(Bool()));val bus=IO(new LocalBus)
  val bootMode=IO(Input(Bool()))
  val released=IO(Output(Bool()));val held=IO(Output(Bool()));val draining=IO(Output(Bool()))
  protected def permitted(origin: UInt): Bool=origin===owner.U
  val up=epochReset_n && reset_n
  val regs=Module(new RegBlock(json));regs.clk:=clk;regs.rst_n:=up
  val adapter=Module(new BusRegAdapter(8,base,0));adapter.clk:=clk;adapter.reset_n:=up
  adapter.bus.req:=bus.req;adapter.bus.bits:=bus.bits
  adapter.bus.bits.origin:=Mux(permitted(bus.bits.origin),0.U,7.U)
  bus.gnt:=adapter.bus.gnt;bus.rvalid:=adapter.bus.rvalid;bus.rdata:=adapter.bus.rdata;bus.err:=adapter.bus.err
  regs.bus<>adapter.registers
  val state=Module(new LiteBootState);state.clk:=clk;state.epochReset_n:=epochReset_n
  state.serviceReset_n:=up;state.quiet:=quiet;state.debugOwned:=debugOwned
  state.releaseCommand:=regs.hw("release_core_key_we").asBool
  state.releaseKey:=regs.hw("release_core_key_wdata")==="h50455246".U
  state.holdCommand:=regs.hw("hold_core_key_we").asBool
  state.holdKey:=regs.hw("hold_core_key_wdata")==="h484f4c44".U
  regs.hw("status_held_d"):=state.held.asUInt
  regs.hw("status_released_d"):=state.released.asUInt
  regs.hw("status_draining_d"):=state.draining.asUInt
  regs.hw("events_command_error_set"):=state.error.asUInt
  regs.hw("boot_mode_uart_recovery_d"):=bootMode.asUInt
  released:=state.released;held:=state.held;draining:=state.draining
}
object EmitBootControl extends App {
  require(args.length==2)
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(new BootControl(args(0)),Array("--target-dir",args(1)),
    Array("--disable-all-randomization","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
