package deadhorse.i2c_host

import circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

object EmitI2cHost extends App {
  require(args.length == 2, "register JSON, output directory")
  Files.createDirectories(Paths.get(args(1)))
  ChiselStage.emitSystemVerilogFile(new I2cHost(args(0)),
    Array("--target-dir", args(1)),
    Array("--disable-all-randomization", "--strip-debug-info", "--lowering-options=disallowLocalVariables,disallowPackedArrays"))
}
