package deadhorse.timing

import chisel3._
import circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

/** Stateless, characterized-cell fixture for the input-to-output timing route. */
class CombTiming extends RawModule {
  val a = IO(Input(Bool()))
  val b = IO(Input(Bool()))
  val out = IO(Output(Bool()))
  out := a ^ b
}

class AliasTiming extends RawModule {
  val a = IO(Input(Bool())); val b = IO(Input(Bool()))
  val out = IO(Output(Bool())); val alias = IO(Output(Bool()))
  val zeros = IO(Output(UInt(8.W)))
  out := a ^ b; alias := out; zeros := 0.U
}

object EmitCombTiming {
  def main(args: Array[String]): Unit = {
    require(args.length == 1)
    val output = Paths.get(args(0)).toAbsolutePath.normalize
    require(output.startsWith(Paths.get("build").toAbsolutePath.normalize))
    Files.createDirectories(output)
    ChiselStage.emitSystemVerilogFile(new CombTiming,
      Array("--target-dir", output.toString),
      Array("--disable-all-randomization", "-strip-debug-info"))
    ChiselStage.emitSystemVerilogFile(new AliasTiming,
      Array("--target-dir", output.toString),
      Array("--disable-all-randomization", "-strip-debug-info"))
  }
}
