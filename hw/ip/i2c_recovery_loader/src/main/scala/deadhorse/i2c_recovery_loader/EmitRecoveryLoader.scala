package deadhorse.i2c_recovery_loader

import circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

object EmitRecoveryLoader extends App {
  require(args.length == 1, "build output directory")
  val output = Paths.get(args(0)).toAbsolutePath.normalize
  require(output.startsWith(Paths.get("build").toAbsolutePath.normalize))
  Files.createDirectories(output)
  ChiselStage.emitSystemVerilogFile(new RecoveryLoader(),
    Array("--target-dir", output.toString),
    Array("--disable-all-randomization", "--strip-debug-info",
      "--lowering-options=disallowLocalVariables,disallowPackedArrays"))
}
