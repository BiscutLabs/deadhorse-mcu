package deadhorse.usb

import chisel3._
import java.nio.file.{Files, Paths}
import _root_.circt.stage.ChiselStage

/** Combinational proof monitor, bound to the original oracle's exact nets.
  * There is no substitute oracle state or input constraint. The selected byte
  * of an uncommitted packet must follow every already-committed byte.
  */
class UsbOutPositionLemma extends RawModule {
  val clock = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val watching = IO(Input(Bool())); val inPacket = IO(Input(Bool()))
  val position = IO(Input(UInt(5.W))); val queued = IO(Input(UInt(5.W)))
  withClockAndReset(clock, (!reset_n).asAsyncReset) {
    when(watching && inPacket) { assert(position >= queued) }
  }
}

object EmitUsbOutPositionLemma {
  def main(args: Array[String]): Unit = {
    require(args.length == 1)
    val root = Paths.get(args(0)).toAbsolutePath.normalize
    require(root.startsWith(Paths.get("build").toAbsolutePath.normalize))
    Files.createDirectories(root)
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new UsbOutPositionLemma),
      Array("--target-dir", root.toString),
      Array("--disable-all-randomization", "--verification-flavor=immediate", "--lower-to-core", "-strip-debug-info"))
  }
}
