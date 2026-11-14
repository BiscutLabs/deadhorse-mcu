package deadhorse.timing

import circt.stage.ChiselStage
import deadhorse.lib.RegBlock
import java.nio.file.{Files, Paths}

/** Timing-only entry point; instantiates the production block unchanged. */
object EmitRegTiming {
  def main(args: Array[String]): Unit = {
    require(args.length == 2, "Usage: EmitRegTiming expanded.json build/<output>")
    val output = Paths.get(args(1)).toAbsolutePath.normalize
    require(output.startsWith(Paths.get("build").toAbsolutePath.normalize))
    Files.createDirectories(output)
    ChiselStage.emitSystemVerilogFile(new RegBlock(args(0)),
      Array("--target-dir", output.toString),
      Array("--disable-all-randomization", "-strip-debug-info"))
  }
}
