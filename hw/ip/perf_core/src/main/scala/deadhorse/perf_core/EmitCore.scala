package deadhorse.perf_core

import circt.stage.ChiselStage
import java.nio.file.{Files,Paths}

object EmitCore {
  def main(args: Array[String]): Unit = {
    require(args.length==1,"Usage: EmitCore build/<output>")
    val output=Paths.get(args(0)).toAbsolutePath.normalize
    require(output.startsWith(Paths.get("build").toAbsolutePath.normalize))
    Files.createDirectories(output)
    ChiselStage.emitSystemVerilogFile(new IbexCore,
      Array("--target-dir",output.toString),
      Array("--disable-all-randomization","-strip-debug-info","--preserve-values=named"))
  }
}
