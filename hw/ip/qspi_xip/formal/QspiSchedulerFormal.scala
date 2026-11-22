package deadhorse.qspi_xip
import chisel3._
import chisel3.util._
import deadhorse.lib.LocalBus
import deadhorse.qspi.QspiCommand
import _root_.circt.stage.ChiselStage

/** Interface scoreboard, independent of the implementation's state encoding.
  * Engine completion/data and client traffic remain arbitrary. This proves
  * safety, not flash progress or the engine's physical pin protocol. */
class QspiSchedulerFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val xip=IO(new LocalBus);val enabled=IO(Input(Bool()))
  val config=IO(Input(new QspiCommand));val command=IO(Input(new QspiCommand))
  val commandValid=IO(Input(Bool()));val engineDone=IO(Input(Bool()))
  val engineBusy=IO(Input(Bool()));val engineResult=IO(Input(UInt(32.W)))
  val s=Module[QspiScheduler](if(variant=="endian") new QspiScheduler {
    override protected def nativeWord(v: UInt): UInt=v
  } else new QspiScheduler)
  s.clk:=clock;s.reset_n:=reset_n;s.xip<>xip;s.enabled:=enabled
  s.readConfig:=config;s.command:=command;s.commandValid:=commandValid
  s.engineDone:=engineDone;s.engineBusy:=engineBusy;s.engineResult:=engineResult
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val readOwed=RegInit(false.B);val commandOwed=RegInit(false.B)
    when(s.xip.rvalid) {readOwed:=false.B}
    when(s.xip.req && s.xip.gnt) {readOwed:=true.B}
    when(s.commandDone) {commandOwed:=false.B}
    when(s.commandValid && s.commandReady) {commandOwed:=true.B}
    val previousEngineResult=RegNext(engineResult,0.U)
    val previousResult=RegNext(s.xip.rdata,0.U)
    val previousCommandResult=RegNext(s.commandResult,0.U)
    val past=RegNext(true.B,false.B)
    if(variant=="cover") {
      cover(s.xip.rvalid && !s.xip.err && s.xip.rdata=/=0.U)
      cover(s.xip.rvalid && s.xip.err)
      cover(s.commandDone && readOwed)
      cover(s.xip.rvalid && !s.xip.err && commandOwed)
    } else {
      assert(!s.xip.rvalid || readOwed)
      assert(!s.commandDone || commandOwed)
      assert(!s.xip.rvalid || !s.xip.err || s.xip.rdata===0.U)
      assert(!s.xip.rvalid || s.xip.err || s.xip.rdata===Cat(
        previousEngineResult(7,0),previousEngineResult(15,8),
        previousEngineResult(23,16),previousEngineResult(31,24)))
      when(past) {
        assert(s.xip.rdata===previousResult || s.xip.rvalid)
        assert(s.commandResult===previousCommandResult || s.commandDone)
      }
    }
  }
}
object EmitQspiSchedulerFormal extends App {
  require(args.length==1)
  for(v<-Seq("correct","endian","cover")) ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new QspiSchedulerFormal(v)),Array("--target-dir",s"${args(0)}/$v"),
    Array("--disable-all-randomization","--disable-opt","--lint-static-asserts=false",
      "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
