package deadhorse.usb

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

/** Observation-only temporal reference, bound to the complete production engine.
  * No environment assumptions, packet restrictions or initialized header memory.
  */
class UsbSampling(role: String, covers: Boolean) extends RawModule {
  val clock = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val ce = IO(Input(Bool())); val busReset = IO(Input(Bool()))
  val state = IO(Input(UInt(7.W))); val cursor = IO(Input(UInt(7.W)))
  val total = IO(Input(UInt(7.W))); val requested = IO(Input(UInt(16.W)))
  val zlpSent = IO(Input(Bool())); val response = IO(Input(UInt(2.W)))
  val configured = IO(Input(Bool()))
  val inReady = IO(Input(Bool())); val inRequest = IO(Input(Bool())); val inAck = IO(Input(Bool()))
  val setup = IO(Input(Bool())); val outReady = IO(Input(Bool()))
  val outValid = IO(Input(Bool())); val outError = IO(Input(Bool()))
  val setupCount = IO(Input(UInt(4.W)))
  val nextCursor = IO(Input(UInt(7.W))); val dataRemaining = IO(Input(Bool()))
  val terminalZlp = IO(Input(Bool())); val readComplete = IO(Input(Bool()))
  val inData = IO(Input(UInt(8.W))); val inValid = IO(Input(Bool()))
  val inZlp = IO(Input(Bool())); val stall = IO(Input(Bool()))
  val sieReset = IO(Input(Bool())); val sieEndpoint = IO(Input(UInt(4.W)))
  val sieState = IO(Input(UInt(4.W))); val sieRxReady = IO(Input(Bool()))
  val sieTxReady = IO(Input(Bool())); val sieRxError = IO(Input(Bool()))
  val sieInReady = IO(Input(Bool()))
  val headerType = IO(Input(UInt(8.W))); val descriptorLength = IO(Input(UInt(7.W)))
  val decodeQ = IO(Input(UInt(20.W))); val decodeNow = IO(Input(UInt(20.W)))

  withClockAndReset(clock, (!reset_n).asAsyncReset) {
    val reading = state === 4.U
    val status = state === 16.U
    val remaining = cursor < total
    val terminal = total < requested && total(2, 0) === 0.U
    val complete = cursor >= total && (cursor === requested || cursor(2, 0) =/= 0.U || zlpSent)
    val enabled = ce && !busReset
    val writeHeader = enabled && state === 2.U && outReady && !setup && !outError && outValid && setupCount < 8.U
    val admit = enabled && state === 2.U && outReady && !setup && !outError && !outValid
    val history = RegInit(0.U(2.W))
    when(ce) { history := Cat(history(0), writeHeader) }
    val sample = ce && sieReset && sieEndpoint === 0.U && !sieRxError && (sieRxReady || sieTxReady)
    val sampleData = sample && (sieState === 8.U || sieState === 9.U) && sieInReady
    // Direct descriptor lookup, without the production ROM/read-select stages.
    val device = Seq(18,1,0,2,2,0,0,8,0,0,0,0,0x10,1,0,0,0,1)
    val config = Seq(9,2,67,0,2,1,0,0x80,0x32,9,4,0,0,1,2,2,1,0,
      5,0x24,0,0x10,1,5,0x24,1,0,1,4,0x24,2,0,5,0x24,6,0,1,
      7,5,0x82,3,8,0,255,9,4,1,0,2,0x0a,0,0,0,7,5,1,2,16,0,0,7,5,0x81,2,16,0,0)
    def lookup(bytes: Seq[Int]): UInt = VecInit(bytes.padTo(128, 0).map(_.U(8.W)))(cursor)
    val directData = MuxLookup(response, 0.U(8.W))(Seq(1.U -> lookup(device),
      2.U -> lookup(config), 3.U -> configured.asUInt))
    if (covers) {
      cover(enabled && reading && inReady && !inRequest && !inAck && remaining)
      cover(sampleData && response === 2.U && cursor > 8.U)
      cover(admit && setupCount === 8.U)
      cover(admit && setupCount < 8.U)
      cover(admit && setupCount > 8.U)
      cover(enabled && state === 2.U && outReady && outError)
      cover(enabled && state === 2.U && outReady && setup && setupCount =/= 0.U)
    } else role match {
      case "lookahead" => when(enabled && reading && inReady) {
        assert(nextCursor === (cursor + 1.U)(6, 0))
        assert(dataRemaining === remaining)
        assert(terminalZlp === terminal)
        assert(readComplete === complete)
      }
      case "outputs" =>
        when(sample) {
          assert(inValid === ((reading && (remaining || terminal)) || status))
          assert(inZlp === (status || (reading && !remaining)))
          assert(stall === (state === 64.U))
        }
        when(sampleData) { assert(inData === directData) }
      case "spacing" => when(admit) {
        assert(!history.orR)
        assert(descriptorLength === Mux(headerType === 1.U, 18.U, 67.U))
        assert(decodeQ === decodeNow)
      }
    }
  }
}

object EmitUsbSampling {
  def main(args: Array[String]): Unit = {
    require(args.length == 2 && Set("lookahead", "outputs", "spacing", "covers")(args(1)))
    val root = Paths.get(args(0)).toAbsolutePath.normalize
    require(root.startsWith(Paths.get("build").toAbsolutePath.normalize)); Files.createDirectories(root)
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new UsbSampling(args(1), args(1) == "covers")),
      Array("--target-dir", root.toString),
      Array("--disable-all-randomization", "--verification-flavor=immediate", "--lower-to-core", "-strip-debug-info"))
  }
}
