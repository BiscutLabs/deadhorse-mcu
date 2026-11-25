package deadhorse.timers
import chisel3._
import _root_.circt.stage.ChiselStage
import deadhorse.aon_timer.AonTimers

class AonTimerFormal(json: String,variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new deadhorse.lib.LocalBus)
  val d=Module[AonTimers](if(variant=="corrupt") new AonTimers(json,formalChecks=true) {
    override protected def loadedDuration(v: UInt): UInt=v^1.U
  } else new AonTimers(json,formalChecks=variant!="cover"))
  d.clk:=clock;d.reset_n:=reset_n;d.bus<>bus;d.owner:=0.U
  if(variant=="cover") withClockAndReset(clock,(!reset_n).asAsyncReset) {cover(d.irq && d.wake)}
}
object EmitIoFormal extends App {
  require(args.length==2,"EmitIoFormal <case> <output>")
  for(v<-Seq("cover","corrupt","correct")) {
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(args(0) match {
      case "aon" => new AonTimerFormal("build/t21/aon_timer/aon_timer_regs.json",v)
      case "wake" => new deadhorse.gpio.GpioWakeFormal(v)
      case "gpio_denied" => new deadhorse.gpio.GpioDeniedFormal("build/t21/gpio/gpio_regs.json",v)
    }),Array("--target-dir",s"${args(1)}/$v"),
      Array("--disable-all-randomization","--disable-opt","--lint-static-asserts=false",
        "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
  }
}
