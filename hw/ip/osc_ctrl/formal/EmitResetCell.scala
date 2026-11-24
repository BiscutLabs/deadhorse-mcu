package deadhorse.osc_ctrl

import chisel3._

/** The production reset-held clock selector and actual routing fault control. */
object EmitResetCell extends App {
  require(args.length==1)
  for(fault<-Seq(false,true)) {
    val d=()=>new ResetBootstrap {
      override def desiredName="ResetBootstrap"
      override protected def clockSelection(held: Bool,raw: Bool): Bool=if(fault) raw else held
    }
    _root_.circt.stage.ChiselStage.emitSystemVerilogFile(d(),
      Array("--target-dir",s"${args(0)}/${if(fault) "fault" else "correct"}"),
      Array("--disable-all-randomization","--strip-debug-info","--preserve-values=named"))
  }
}
