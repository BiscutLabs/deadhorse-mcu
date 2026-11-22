package deadhorse.boot_control
import chisel3._
import chisel3.util._
import deadhorse.lib._

class BootControl(json: String,base: BigInt=0,owner: Int=0) extends RawModule {
  val clk=IO(Input(Clock()));val epochReset_n=IO(Input(Bool()));val reset_n=IO(Input(Bool()))
  val startAccepted=IO(Input(Bool()));val bus=IO(new LocalBus)
  val released=IO(Output(Bool()))
  protected def permitted(origin: UInt): Bool=origin===owner.U
  val up=epochReset_n && reset_n
  val regs=Module(new RegBlock(json));regs.clk:=clk;regs.rst_n:=up
  val adapter=Module(new BusRegAdapter(8,base,0));adapter.clk:=clk;adapter.reset_n:=up
  adapter.bus.req:=bus.req;adapter.bus.bits:=bus.bits
  adapter.bus.bits.origin:=Mux(permitted(bus.bits.origin),0.U,7.U)
  bus.gnt:=adapter.bus.gnt;bus.rvalid:=adapter.bus.rvalid;bus.rdata:=adapter.bus.rdata;bus.err:=adapter.bus.err
  regs.bus<>adapter.registers
  val state=Module(new BootRelease);state.clk:=clk;state.epochReset_n:=epochReset_n
  state.serviceReset_n:=up;state.startAccepted:=startAccepted
  state.command:=regs.hw("release_core_key_we").asBool
  state.keyGood:=regs.hw("release_core_key_wdata")==="h50455246".U
  regs.hw("status_boot_seen_d"):=state.bootSeen.asUInt
  regs.hw("status_released_d"):=state.released.asUInt
  regs.hw("events_command_error_set"):=state.error.asUInt
  released:=state.released
}
object EmitBootControl extends App {
  require(args.length==2)
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(new BootControl(args(0)),Array("--target-dir",args(1)),
    Array("--disable-all-randomization","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
