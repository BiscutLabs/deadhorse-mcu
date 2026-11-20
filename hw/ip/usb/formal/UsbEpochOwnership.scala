package deadhorse.usb

import chisel3._
import java.nio.file.{Files, Paths}
import _root_.circt.stage.ChiselStage

/** Observer-only upper bound for the eight-byte OUT induction. Rejected
  * overlength packets may wrap their diagnostic counter, so the bound applies
  * only while the current packet can still commit. It is proved, not assumed.
  */
class UsbEpochOwnership extends RawModule {
  val clock = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val watching = IO(Input(Bool())); val inPacket = IO(Input(Bool())); val reject = IO(Input(Bool()))
  val position = IO(Input(UInt(5.W))); val queued = IO(Input(UInt(5.W))); val packet = IO(Input(UInt(4.W)))
  withClockAndReset(clock, (!reset_n).asAsyncReset) {
    when(watching && inPacket && !reject) { assert(position < (queued +& packet)) }
  }
}

object EmitUsbEpochOwnership {
  def main(args: Array[String]): Unit = {
    require(args.length == 1)
    val root = Paths.get(args(0)).toAbsolutePath.normalize
    require(root.startsWith(Paths.get("build").toAbsolutePath.normalize)); Files.createDirectories(root)
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new UsbEpochOwnership),
      Array("--target-dir", root.toString),
      Array("--disable-all-randomization", "--verification-flavor=immediate", "--lower-to-core", "-strip-debug-info"))
  }
}
