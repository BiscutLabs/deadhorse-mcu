package deadhorse.osc_ctrl

import chisel3._
import deadhorse.lib.ClockGateTarget

object EmitOscTiming extends App {
  require(args.length==2)
  val blocks=Seq[(String,()=>RawModule)](
    "control"->(()=>new OscCtrl(args(0))),"stability"->(()=>new OscStability),
    "divider"->(()=>new OscDivider),"gate"->(()=>new OscMainGate(ClockGateTarget.Asic)),
    "reset"->(()=>new ResetBootstrap),"causes"->(()=>new ResetCauses),"sleep"->(()=>new OscSleepTransfer))
  for((name,make)<-blocks) _root_.circt.stage.ChiselStage.emitSystemVerilogFile(make(),
    Array("--target-dir",s"${args(1)}/$name"),Array("--disable-all-randomization","--strip-debug-info",
      "--preserve-values=named","--verification-flavor=immediate","--lower-to-core"))
}
