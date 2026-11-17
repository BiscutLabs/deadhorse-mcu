package deadhorse.spi_host

import circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

object EmitSpiHost {
  def main(args: Array[String]): Unit = {
    require(args.length == 2, "EmitSpiHost build/<map.json> build/<output>")
    val out = Paths.get(args(1)).toAbsolutePath.normalize
    require(out.startsWith(Paths.get("build").toAbsolutePath.normalize))
    Files.createDirectories(out)
    ChiselStage.emitSystemVerilogFile(new SpiHost(args(0)), Array("--target-dir", out.toString),
      Array("--disable-all-randomization", "-strip-debug-info", "--preserve-values=named"))
  }
}
