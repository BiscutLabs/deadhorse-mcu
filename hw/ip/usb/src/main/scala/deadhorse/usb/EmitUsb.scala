package deadhorse.usb

import chisel3.RawModule
import circt.stage.ChiselStage
import java.nio.file.{Files,Paths}

object EmitUsb {
  def main(args: Array[String]): Unit = {
    require(args.length == 1 || args.length == 2)
    val output=Paths.get(args(0)).toAbsolutePath.normalize
    require(output.startsWith(Paths.get("build").toAbsolutePath.normalize))
    def emit(name: String, module: => RawModule): Unit = {
      val directory=output.resolve(name); Files.createDirectories(directory)
      ChiselStage.emitSystemVerilogFile(module,Array("--target-dir",directory.toString),
        Array("--disable-all-randomization","-strip-debug-info","--preserve-values=named"))
    }
    emit("control",new UsbControl)
    emit("in",new UsbInBuffer)
    emit("out",new UsbOutBuffer)
    emit("engine",new UsbEngine)
    emit("resume",new UsbResume)
    if(args.length == 2) {
      emit("registers",new UsbRegisters(args(1)))
      emit("usb",new Usb(args(1)))
      emit("stub",new deadhorse.stubs.UsbStub(args(1)))
    }
  }
}
