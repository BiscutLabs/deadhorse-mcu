package deadhorse.bus

import chisel3.RawModule
import circt.stage.ChiselStage
import deadhorse.lib._
import deadhorse.bus_bridge._
import deadhorse.mailbox._
import java.nio.file.{Files, Paths}

/** Emit real production clock-domain modules, without timing-only cutpoints. */
object EmitBusTiming {
  def main(args: Array[String]): Unit = {
    require(args.length == 2, "Usage: EmitBusTiming build/<output> build/<mailbox_regs.json>")
    val output = Paths.get(args(0)).toAbsolutePath.normalize
    require(output.startsWith(Paths.get("build").toAbsolutePath.normalize))
    val options = Array("--disable-all-randomization", "-strip-debug-info", "--preserve-values=named")
    def emit(name: String, dut: => RawModule): Unit = {
      val dir = output.resolve(name); Files.createDirectories(dir)
      ChiselStage.emitSystemVerilogFile(dut, Array("--target-dir", dir.toString), options)
    }
    emit("fabric", new BusFabric(3, Seq(BusRegion(0x1000, 0x1000, 128), BusRegion(0x2000, 0x1000, 131080))))
    emit("source", new BridgeSource(131072))
    emit("target", new BridgeTarget)
    emit("arbiter", new DirectionArbiter)
    for (owner <- 0 to 1) emit(s"mailbox$owner", new MailboxEndpoint(args(1), owner))
    for (width <- Seq(32, 33, 72)) {
      emit(s"write$width", new CdcWrite(width, 2))
      emit(s"read$width", new CdcRead(width, 2))
    }
    emit("reset", new ResetRelease)
    for (width <- Seq(1, 2)) emit(s"sync$width", new CdcSync(width))
  }
}
