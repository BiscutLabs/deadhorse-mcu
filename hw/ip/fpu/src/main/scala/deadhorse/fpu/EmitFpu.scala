package deadhorse.fpu

import circt.stage.ChiselStage

object EmitFpu extends App {
  require(args.length == 1)
  ChiselStage.emitSystemVerilogFile(new Fpu, Array("--target-dir", args(0)),
    Array("--disable-all-randomization", "--strip-debug-info", "--preserve-values=named"))
}
