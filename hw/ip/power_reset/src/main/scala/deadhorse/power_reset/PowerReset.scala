package deadhorse.power_reset

import chisel3._
import chisel3.util.Cat
import deadhorse.lib._

/** Atomic, keyed digital selection; the macro owns analog switching safety. */
class BrownoutSelect extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val selection=IO(Input(UInt(2.W)));val key=IO(Input(UInt(32.W)));val apply=IO(Input(Bool()))
  val threshold=IO(Output(UInt(2.W)));val invalid=IO(Output(Bool()))
  protected def acceptKey(value: Bool): Bool=value
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val active=RegInit(false.B);val error=RegInit(false.B)
    val valid=acceptKey(key==="h42524f57".U) && !selection(1)
    error:=apply && !valid
    when(apply && valid) {active:=selection(0)}
    threshold:=Cat(false.B,active);invalid:=error
  }
}

/** AON-local configuration. Physical threshold switching follows the explicit
  * analog macro guarantee; digital proof does not qualify analog transients. */
class PowerReset(json: String,base: BigInt=BigInt("40000500",16)) extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new LocalBus)
  val causes=IO(Input(UInt(6.W)));val threshold=IO(Output(UInt(2.W)))
  protected def makeSelector(): BrownoutSelect=new BrownoutSelect
  val regs=Module(new RegBlock(json));regs.clk:=clk;regs.rst_n:=reset_n
  val adapter=Module(new BusRegAdapter(8,base,1))
  adapter.clk:=clk;adapter.reset_n:=reset_n;adapter.bus<>bus;regs.bus<>adapter.registers
  val control=Module(makeSelector())
  control.clk:=clk;control.reset_n:=reset_n
  control.selection:=regs.hw("threshold_selection_q")
  control.key:=regs.hw("apply_key_wdata");control.apply:=regs.hw("apply_key_we").asBool
  threshold:=control.threshold;regs.hw("active_selection_d"):=control.threshold
  regs.hw("events_invalid_set"):=control.invalid
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    regs.hw("reason_causes_d"):=RegNext(causes,0.U)
  }
}

object EmitPowerReset extends App {
  require(args.length==2)
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(new PowerReset(args(0)),
    Array("--target-dir",args(1)),Array("--disable-all-randomization","--strip-debug-info",
      "--preserve-values=named","--verification-flavor=immediate","--lower-to-core"))
}
