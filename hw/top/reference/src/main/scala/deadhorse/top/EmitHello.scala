package deadhorse.top

import circt.stage.ChiselStage
import deadhorse.lib.Hello
import java.nio.file.{Files, Paths}

object EmitHello {
  def main(args: Array[String]): Unit = {
    require(args.length == 1, "Usage: EmitHello build/<output>")
    val output = Paths.get(args(0)).toAbsolutePath.normalize
    require(output.startsWith(Paths.get("build").toAbsolutePath.normalize), "Output must be under build/")
    Files.createDirectories(output)
    ChiselStage.emitSystemVerilogFile(new Hello, Array("--target-dir", output.toString),
      Array("--disable-all-randomization", "-strip-debug-info"))
  }
}
