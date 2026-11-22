package deadhorse.gpio
import chisel3._
import deadhorse.lib.LocalBus
import _root_.circt.stage.ChiselStage

/** Conservative logic screen: both domains tied to one root. Not CDC signoff. */
class GpioTiming(json: String) extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new LocalBus)
  val owner=IO(Input(UInt(3.W)));val pinsIn=IO(Input(UInt(3.W)))
  val pinsOut=IO(Output(UInt(3.W)));val pinsEnable=IO(Output(UInt(3.W)))
  val irq=IO(Output(Bool()));val wake=IO(Output(Bool()));val clockHold=IO(Output(Bool()))
  val d=Module(new Gpio(json));d.clk:=clk;d.aonClock:=clk;d.reset_n:=reset_n;d.aonReset_n:=reset_n
  d.bus<>bus;d.owner:=owner;d.pinsIn:=pinsIn
  pinsOut:=d.pinsOut;pinsEnable:=d.pinsEnable;irq:=d.irq;wake:=d.wake;clockHold:=d.clockHold
}
object EmitGpioTiming extends App {
  require(args.length==2)
  ChiselStage.emitSystemVerilogFile(new GpioTiming(args(0)),Array("--target-dir",args(1)),
    Array("--disable-all-randomization","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
