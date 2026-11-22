package deadhorse.adc
import _root_.circt.stage.ChiselStage
object EmitAdcEngine extends App {
  require(args.length==2 && Set("raw","legacy")(args(0)))
  ChiselStage.emitSystemVerilogFile(new ClockedSpiAdc(AdcParameters(),autonomous=false,rawOnly=args(0)=="raw"),
    Array("--target-dir",args(1)),Array("--disable-all-randomization","--strip-debug-info",
      "--verification-flavor=immediate","--lower-to-core"))
}
