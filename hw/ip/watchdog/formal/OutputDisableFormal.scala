package deadhorse.watchdog
import chisel3._
import deadhorse.pwm.PwmBreak
import deadhorse.pinmux.PinmuxPad
import _root_.circt.stage.ChiselStage

class PwmBreakFormal(variant: String) extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val idle=IO(Input(Bool()));val epochReady=IO(Input(Bool()));val stop=IO(Input(UInt(9.W)))
  val d=Module[PwmBreak](if(variant=="corrupt") new PwmBreak {
    override protected def acknowledged(v: UInt): UInt=511.U
  } else new PwmBreak)
  d.clk:=clk;d.reset_n:=reset_n;d.idle:=idle;d.stop:=stop;d.epochReady:=epochReady
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val past=RegNext(true.B,false.B);val oldReady=RegNext(d.ready,false.B)
    val oldPermit=RegNext(d.permit,0.U);val oldStop=RegNext(stop);val oldIdle=RegNext(idle)
    val oldEpoch=RegNext(epochReady,false.B)
    if(variant=="cover") {cover(d.permit===1.U);cover(d.permit===511.U)}
    else {
      assert((d.permit & oldPermit)===oldPermit)
      when(past) {
        assert(d.ready===(oldEpoch && (oldReady || oldIdle)))
        assert(d.permit===Mux(oldReady && oldEpoch,oldPermit | oldStop,oldPermit))
      }
    }
  }
}
class PadDisableFormal(variant: String) extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val watchdogReset_n=IO(Input(Bool()))
  val select=IO(Input(UInt(2.W)));val values=IO(Input(UInt(3.W)));val enables=IO(Input(UInt(3.W)))
  val d=Module(new PinmuxPad(watchdog=true));d.clk:=clk;d.reset_n:=reset_n
  d.watchdogReset_n.get:=(if(variant=="corrupt") true.B else watchdogReset_n)
  d.select:=select;d.values:=values;d.enables:=enables
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val past=RegNext(true.B,false.B);val previous=RegNext(select,0.U)
    val stable=RegNext(select===previous,false.B)
    val oldValues=RegNext(values);val oldEnables=RegNext(enables)
    val oldWatchdog=RegNext(watchdogReset_n,false.B)
    val enabled=stable && previous=/=0.U && oldEnables(previous-1.U) &&
      (previous=/=3.U || oldWatchdog && watchdogReset_n)
    if(variant=="cover") {
      cover(previous===3.U && d.enable);cover(previous===1.U && !watchdogReset_n && d.enable)
      cover(previous===3.U && !watchdogReset_n && !d.enable)
    } else when(past) {
      assert(d.enable===enabled)
      assert(d.value===(enabled && oldValues(previous-1.U)))
    }
  }
}
object EmitOutputDisableFormal extends App {
  require(args.length==2)
  for(v<-Seq("correct","corrupt","cover")) ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(
    if(args(0)=="break") new PwmBreakFormal(v) else {require(args(0)=="pad");new PadDisableFormal(v)}),
    Array("--target-dir",s"${args(1)}/$v"),Array("--disable-all-randomization","--disable-opt",
      "--lint-static-asserts=false","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
