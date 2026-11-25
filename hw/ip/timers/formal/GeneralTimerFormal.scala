package deadhorse.timers
import chisel3._
import deadhorse.lib.LocalBus
import _root_.circt.stage.ChiselStage

class GeneralTimerFormal(json: String,variant: String,mhz: Int=8) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new LocalBus)
  val capture=IO(Input(UInt(12.W)));val valid=IO(Input(UInt(12.W)));val ack=IO(Input(UInt(9.W)))
  val d=Module(new GeneralTimers(json,mainMHz=mhz,formalChecks=true) {
    override protected def timeValue(v: UInt): UInt=if(variant=="time") v^1.U else v
    override protected def holdValue(v: Bool): Bool=if(variant=="hold") !v else v
    override protected def adoptCompare(v: Bool): Bool=if(variant=="early") true.B else v
    override protected def output(v: Bool): Bool=if(variant=="output") !v else v
    override protected def timestamp(v: UInt): UInt=if(variant=="capture") v^1.U else v
  })
  d.clk:=clock;d.reset_n:=reset_n;d.bus<>bus;d.owner:=1.U
  d.captureIn:=capture;d.captureValid:=valid;d.dmaAck:=ack
}
object EmitGeneralTimerFormal extends App {
  require(args.length==1)
  for(v<-Seq("correct","early","output","capture","time","hold","correct9"))
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new GeneralTimerFormal("build/t21/timers/timers_regs.json",v,if(v=="correct9") 9 else 8)),
      Array("--target-dir",s"${args(0)}/$v"),Array("--disable-all-randomization","--disable-opt",
        "--lint-static-asserts=false","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
