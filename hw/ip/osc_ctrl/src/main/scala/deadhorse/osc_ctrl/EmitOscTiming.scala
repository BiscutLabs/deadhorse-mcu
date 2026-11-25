package deadhorse.osc_ctrl

import chisel3._
import deadhorse.lib.ClockGateTarget

object EmitOscTiming extends App {
  require(args.length==2 || args.length==3 && args(2)=="consolidated")
  val shared=args.length==3
  val blocks=Seq[(String,()=>RawModule)](
    "control"->(()=>new OscCtrl(args(0),withWarmInitialize=shared)),"stability"->(()=>new OscStability(qualifiedReset=shared)),
    "divider"->(()=>new OscDivider),"gate"->(()=>new OscMainGate(ClockGateTarget.Asic,withClear=shared)),
    "reset"->(()=>new ResetBootstrap(qualifiedResets=shared)),"causes"->(()=>new ResetCauses(qualifiedResets=shared)),"sleep"->(()=>new OscSleepTransfer(qualifiedResets=shared)))
  for((name,make)<-blocks) _root_.circt.stage.ChiselStage.emitSystemVerilogFile(make(),
    Array("--target-dir",s"${args(1)}/$name"),Array("--disable-all-randomization","--strip-debug-info",
      "--preserve-values=named","--verification-flavor=immediate","--lower-to-core"))
}
