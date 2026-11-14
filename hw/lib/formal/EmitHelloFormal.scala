package deadhorse.lib

import chisel3._
import circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

object EmitHelloFormal {
  def main(args: Array[String]): Unit = {
    require(args.length == 1, "Usage: EmitHelloFormal build/<output>")
    val output = Paths.get(args(0)).toAbsolutePath.normalize
    require(output.startsWith(Paths.get("build").toAbsolutePath.normalize))
    Files.createDirectories(output)
    for (variant <- Seq("correct", "wrong_increment", "wrong_reset", "cover", "cover_query")) {
      def circuit = chisel3.layer.elideBlocks(new HelloFormal(variant))
      val dir = output.resolve(variant)
      Files.createDirectories(dir)
      if (variant != "cover_query") {
        ChiselStage.emitSystemVerilogFile(circuit,
          Array("--target-dir", dir.toString), Array("--disable-all-randomization",
            "--verification-flavor=immediate", "--lower-to-core", "-strip-debug-info"))
      }
      if (variant != "cover") {
        Files.writeString(dir.resolve("HelloFormal.btor2"), ChiselStage.emitBtor2(circuit,
          Array.empty[String], Array("--lower-to-core", "--verification-flavor=immediate")))
      }
    }
  }
}
