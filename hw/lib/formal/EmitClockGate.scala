package deadhorse.lib

import circt.stage.ChiselStage
import java.nio.file.{Files,Paths}

object EmitClockGate {
  def main(args: Array[String]): Unit = {
    require(args.length==1,"Usage: EmitClockGate build/<output>")
    val output=Paths.get(args(0)).toAbsolutePath.normalize
    require(output.startsWith(Paths.get("build").toAbsolutePath.normalize))
    val options=Array("--disable-all-randomization","-strip-debug-info","--preserve-values=named")
    for((name,target)<-Seq("asic"->ClockGateTarget.Asic,"model"->ClockGateTarget.Model)) {
      val dir=output.resolve(name); Files.createDirectories(dir)
      val binding=if(target==ClockGateTarget.Model) Array(
        "--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
        "--ckg-enable=en_i","--ckg-test-enable=test_en_i") else Array.empty[String]
      ChiselStage.emitSystemVerilogFile(new ClockGate(target),Array("--target-dir",dir.toString),options++binding)
    }
  }
}
