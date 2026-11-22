package deadhorse.pwm
import _root_.circt.stage.ChiselStage
object EmitPwm extends App {
  require(args.length==2,"EmitPwm <regmap-json> <output>")
  ChiselStage.emitSystemVerilogFile(new Pwm(args(0)),Array("--target-dir",args(1)),
    Array("--disable-all-randomization","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
