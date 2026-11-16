package deadhorse.perf_core.formal

import circt.stage.ChiselStage
import deadhorse.perf_core.IbexIfStage
import java.nio.file.Paths

/** Retain the complete IF interface for conditional equivalence qualification. */
object EmitIfNoF {
  def main(args: Array[String]): Unit = {
    require(args.length == 1, "Usage: EmitIfNoF build/<output>")
    val output = Paths.get(args(0)).toAbsolutePath.normalize
    require(output.startsWith(Paths.get("build").toAbsolutePath.normalize))
    ChiselStage.emitSystemVerilogFile(new IbexIfStage(RegisteredRedirect=true, WithF=true),
      Array("--target-dir", output.toString),
      Array("--disable-all-randomization", "-strip-debug-info", "--preserve-values=named"))
  }
}
