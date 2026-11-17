package deadhorse.uart

import chisel3.RawModule
import circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

object EmitUart {
  def main(args: Array[String]): Unit = {
    require(args.length == 2, "Usage: EmitUart build/<uart_regs.json> build/<output>")
    val output = Paths.get(args(1)).toAbsolutePath.normalize
    require(output.startsWith(Paths.get("build").toAbsolutePath.normalize))
    val options = Array("--disable-all-randomization", "-strip-debug-info", "--preserve-values=named")
    def emit(name: String, module: => RawModule): Unit = {
      val directory = output.resolve(name); Files.createDirectories(directory)
      ChiselStage.emitSystemVerilogFile(module, Array("--target-dir", directory.toString), options)
    }
    emit("uart", new Uart(args(0)))
    emit("wake", new UartWake)
    emit("bank", new UartBank(args(0)))
  }
}
