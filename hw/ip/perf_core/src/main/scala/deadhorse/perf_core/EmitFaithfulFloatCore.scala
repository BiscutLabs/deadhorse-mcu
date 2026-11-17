package deadhorse.perf_core

import circt.stage.ChiselStage
import deadhorse.lib.ClockGateTarget
import java.nio.file.{Files,Paths}

/** T13 faithful-pipeline RV32IMFC candidate; the baseline and integer-only emitters remain available. */
object EmitFaithfulFloatCore {
  def main(args: Array[String]): Unit = {
    require(args.length==1,"Usage: EmitFaithfulFloatCore build/<output>")
    val output=Paths.get(args(0)).toAbsolutePath.normalize
    require(output.startsWith(Paths.get("build").toAbsolutePath.normalize))
    val options=Array("--disable-all-randomization","-strip-debug-info","--preserve-values=named")
    for((name,target,trace)<-Seq(("model",ClockGateTarget.Model,true),
      ("asic",ClockGateTarget.Asic,false))) {
      val directory=output.resolve(name); Files.createDirectories(directory)
      val binding=if(target==ClockGateTarget.Model) Array("--ckg-name=prim_generic_clock_gating",
        "--ckg-input=clk_i","--ckg-output=clk_o","--ckg-enable=en_i","--ckg-test-enable=test_en_i") else Array.empty[String]
      ChiselStage.emitSystemVerilogFile(new IbexTop(target,trace,RegisteredExecution=false,WithF=true) {
        // The verification-only reference top name stays isolated from the
        // physical source inventory. This only names the same Chisel hierarchy.
        override def desiredName = if(target==ClockGateTarget.Asic) "DeadhorsePerfCore" else "ibex_top"
      },
        Array("--target-dir",directory.toString),options++binding)
    }
  }
}
