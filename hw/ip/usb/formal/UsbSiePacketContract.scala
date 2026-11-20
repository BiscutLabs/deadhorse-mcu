package deadhorse.usb

import chisel3._
import chisel3.util._
import java.nio.file.{Files, Paths}
import _root_.circt.stage.ChiselStage

/** Observation only: instantiate the exact production engine and its patched
  * SIE/PHY. Arbitrary request/retry/ACK (including empty ACK) is allowed by the
  * epoch packet model; a normal byte consume must still observe valid data.
  */
class UsbSiePacketContract(fault: Int = 0) extends UsbEngine {
  require(fault >= 0 && fault <= 3)
  // Verification-only DUT mutations; production UsbEngine is unchanged.
  if (fault == 1) { in.request := true.B }
  if (fault == 2) { in.consume := true.B; in.request := false.B; in.acknowledge := false.B }
  if (fault == 3) { out.receiveReady := true.B }
  val violationsSeen = IO(Output(UInt(4.W)))
  val trafficSeen = IO(Output(UInt(4.W)))
  withClockAndReset(clk, (!engineReset).asAsyncReset) {
    val endpoint = RegEnable(sie.io.endp_o, 0.U, cadence.preEnable)
    val inActive = cadence.enable && in.reset_n
    val outActive = cadence.enable && out.reset_n
    val normal = in.consume && !in.request && !in.acknowledge
    val broken = Cat(outActive && out.receiveReady && endpoint =/= 1.U,
      inActive && normal && !in.valid,
      inActive && in.consume && endpoint =/= 1.U,
      inActive && in.request && !in.consume)
    val seen = RegInit(0.U(4.W)); seen := seen | broken; violationsSeen := seen
    val traffic = RegInit(0.U(4.W))
    traffic := traffic | Cat(outActive && out.receiveReady,
      inActive && in.consume && in.acknowledge && !in.request,
      inActive && normal, inActive && in.request)
    trafficSeen := traffic
    if (fault == 0) {
      when(inActive) {
        when(in.request) { assert(in.consume) }
        when(in.consume) { assert(endpoint === 1.U) }
        when(normal) { assert(in.valid) }
      }
      when(outActive && out.receiveReady) { assert(endpoint === 1.U) }
    }
  }
}

object EmitUsbSiePacketContract {
  def main(args: Array[String]): Unit = {
    require(args.length == 1)
    val root = Paths.get(args(0)).toAbsolutePath.normalize
    require(root.startsWith(Paths.get("build").toAbsolutePath.normalize))
    Files.createDirectories(root)
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new UsbSiePacketContract),
      Array("--target-dir", root.toString),
      Array("--disable-all-randomization", "--verification-flavor=immediate", "--lower-to-core", "-strip-debug-info"))
  }
}
