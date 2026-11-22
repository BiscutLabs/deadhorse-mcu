package deadhorse.adc
import _root_.circt.stage.ChiselStage
object EmitAdc extends App {
  require(args.length==2)
  ChiselStage.emitSystemVerilogFile(new Adc(args(0)),Array("--target-dir",args(1)),
    Array("--disable-all-randomization","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
