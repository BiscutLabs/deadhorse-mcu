package deadhorse.adc
import chisel3._
import _root_.circt.stage.ChiselStage

/** Match the asynchronous reset inferred by the production Adc wrapper. */
class AdcEngineTiming(raw: Boolean)
    extends ClockedSpiAdc(AdcParameters(),autonomous=false,rawOnly=raw) with RequireAsyncReset

object EmitAdcEngineTiming extends App {
  require(args.length==2 && Set("raw","legacy")(args(0)))
  ChiselStage.emitSystemVerilogFile(new AdcEngineTiming(args(0)=="raw"),
    Array("--target-dir",args(1)),Array("--disable-all-randomization","--strip-debug-info",
      "--verification-flavor=immediate","--lower-to-core"))
}
