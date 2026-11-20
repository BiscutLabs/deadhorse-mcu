package deadhorse.usb

import chisel3._
import java.nio.file.{Files, Paths}
import _root_.circt.stage.ChiselStage

/** Strengthen the original IN service proof without changing its oracle.
  * A retained packet owns at least one committed byte, even after its last
  * speculative read. Only ACK/reset releases that ownership.
  */
class UsbInProgressFormal(variant: String, bytes: Int)
    extends UsbInFormal(variant, None, true, false, bytes) {
  withClockAndReset(clock, (!reset_n).asAsyncReset) {
    val p = d.proof.get
    if (variant == "cover") {
      cover(p.pending && p.head =/= p.visibleTail && cadence.enable && d.request)
    } else {
      when(p.pending) { assert(p.head =/= p.visibleTail) }
    }
  }
}

object EmitUsbPacketProgress {
  def main(args: Array[String]): Unit = {
    require(args.length == 2)
    val root = Paths.get(args(0)).toAbsolutePath.normalize
    require(root.startsWith(Paths.get("build").toAbsolutePath.normalize))
    val bytes = args(1).toInt
    require(Set(8, 16).contains(bytes))
    for (variant <- Seq("correct", "cover")) {
      val dir = root.resolve(variant); Files.createDirectories(dir)
      ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new UsbInProgressFormal(variant, bytes)),
        Array("--target-dir", dir.toString),
        Array("--disable-all-randomization", "--verification-flavor=immediate", "--lower-to-core", "-strip-debug-info"))
    }
  }
}
