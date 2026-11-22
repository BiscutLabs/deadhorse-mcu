package deadhorse.gpio

import _root_.circt.stage.ChiselStage
object EmitGpio extends App {
  require(args.length==2)
  ChiselStage.emitSystemVerilogFile(new Gpio(args(0)),Array("--target-dir",args(1)),
    Array("--disable-all-randomization","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
