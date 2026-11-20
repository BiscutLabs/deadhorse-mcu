package deadhorse.usb

import chisel3._
import java.nio.file.{Files, Paths}
import _root_.circt.stage.ChiselStage

/** Observation only: individually valid modular intervals must not overlap.
  * The counter bound uses separately proved counter/pointer correspondences.
  * No state, environment assumption, or DUT input is introduced here.
  */
class UsbOutOccupancyLemma extends RawModule {
  val clock = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val head = IO(Input(UInt(4.W))); val tail = IO(Input(UInt(4.W)))
  val speculative = IO(Input(UInt(4.W))); val reject = IO(Input(Bool()))
  val queued = IO(Input(UInt(5.W))); val packet = IO(Input(UInt(4.W)))
  val appValid = IO(Input(Bool()))
  def distance(a: UInt, b: UInt): UInt = Mux(b >= a, b - a, 9.U(5.W) + b - a)
  withClockAndReset(clock, (!reset_n).asAsyncReset) {
    when(!reject) {
      assert((distance(head, tail) +& distance(tail, speculative)) <= 8.U)
      assert((queued +& packet) <= (8.U(5.W) +& appValid.asUInt))
    }
  }
}

object EmitUsbOutOccupancyLemma {
  def main(args: Array[String]): Unit = {
    require(args.length == 1)
    val root = Paths.get(args(0)).toAbsolutePath.normalize
    require(root.startsWith(Paths.get("build").toAbsolutePath.normalize)); Files.createDirectories(root)
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new UsbOutOccupancyLemma),
      Array("--target-dir", root.toString),
      Array("--disable-all-randomization", "--verification-flavor=immediate", "--lower-to-core", "-strip-debug-info"))
  }
}
