package deadhorse.perf_core

import circt.stage.ChiselStage
import deadhorse.lib.ClockGateTarget
import java.nio.file.{Files,Paths}

/** Faithful timing trial: same ASIC boundary as EmitRegisteredCore, no retiming. */
object EmitFaithfulCore {
  def main(args: Array[String]): Unit = {
    require(args.length==1,"Usage: EmitFaithfulCore build/<output>")
    val output=Paths.get(args(0)).toAbsolutePath.normalize
    require(output.startsWith(Paths.get("build").toAbsolutePath.normalize))
    val options=Array("--disable-all-randomization","-strip-debug-info","--preserve-values=named")
    for((name,target,trace)<-Seq(("model",ClockGateTarget.Model,true),
      ("asic",ClockGateTarget.Asic,false))) {
      val directory=output.resolve(name); Files.createDirectories(directory)
      val binding=if(target==ClockGateTarget.Model) Array("--ckg-name=prim_generic_clock_gating",
        "--ckg-input=clk_i","--ckg-output=clk_o","--ckg-enable=en_i","--ckg-test-enable=test_en_i") else Array.empty[String]
      ChiselStage.emitSystemVerilogFile(new IbexTop(target,trace,RegisteredExecution=false,WithF=false) {
        override def desiredName = if(target==ClockGateTarget.Asic) "DeadhorsePerfCore" else "ibex_top"
      },
        Array("--target-dir",directory.toString),options++binding)
    }
  }
}
