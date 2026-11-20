package deadhorse.usb

import chisel3._
import deadhorse.lib.ResetRelease
import java.nio.file.{Files, Paths}
import _root_.circt.stage.ChiselStage

/** Reuse the original byte oracle and assertions, but release the buffer
  * independently of the running production cadence. Zero-byte ACK is allowed.
  * No input assumptions are introduced.
  */
class UsbInEpochSubject(variant: String, bytes: Int, sparse: Boolean = false)
    extends UsbInFormal(variant, None, true, sparse, bytes) {
  val cadenceReset_n = IO(Input(Bool()))
  cadence.reset_n := cadenceReset_n
  val pendingWrite = IO(Output(Bool())); pendingWrite := d.proof.get.stagingValid
  val stalled = IO(Output(Bool())); stalled := d.valid && operation === 0.U
  d.acknowledge := operation === 3.U
  d.consume := (operation === 1.U && d.valid) || operation === 2.U || operation === 3.U
  withClockAndReset(clock, (!reset_n).asAsyncReset) {
    val age = RegInit(0.U(2.W)); when(age =/= 3.U) { age := age + 1.U }
    if (variant != "cover") {
      when(cadence.enable && d.valid) { assert(age === 3.U) }
      when(d.proof.get.pending) { assert(d.proof.get.head =/= d.proof.get.visibleTail) }
      if (sparse) {
        val tag = RegNext(RegNext(RegNext(d.proof.get.speculative)))
        when(age === 3.U && cadence.enable) { assert(tag === d.proof.get.speculative) }
      }
    } else {
      cover(cadence.enable && d.acknowledge && d.proof.get.head === d.proof.get.speculative)
    }
  }
}

class UsbOutEpochSubject(variant: String, bytes: Int, sparse: Boolean = false)
    extends UsbOutFormal(variant, None, true, sparse, false, bytes) {
  val cadenceReset_n = IO(Input(Bool()))
  cadence.reset_n := cadenceReset_n
  val pendingWrite = IO(Output(Bool())); pendingWrite := d.proof.get.speculative =/= d.proof.get.tail
  val stalled = IO(Output(Bool())); stalled := d.appValid && !ready
  // The actual SIE forwards bytes even after an OUT packet exceeds MPS.
  d.receiveValid := operation === 1.U
  withClockAndReset(clock, (!reset_n).asAsyncReset) {
    val age = RegInit(0.U(2.W)); when(age =/= 3.U) { age := age + 1.U }
    val p = d.proof.get
    val end = cadence.enable && d.receiveReady && (!d.receiveValid || d.receiveError)
    val byte = cadence.enable && d.receiveReady && d.receiveValid && !d.receiveError
    val longCount = RegInit(0.U((UsbPacketGeometry(bytes).pointerBits + 1).W))
    val wrapLength = (1 << UsbPacketGeometry(bytes).pointerBits) + 1
    when(end) { longCount := 0.U }
      .elsewhen(byte && longCount < wrapLength.U) { longCount := longCount + 1.U }
    val previousRejected = RegNext(p.reject, false.B)
    val previousEnd = RegNext(end, false.B)
    val previousTail = RegNext(p.tail, 0.U)
    val wrappedAbort = RegInit(false.B)
    when(end && longCount === wrapLength.U && p.reject) { wrappedAbort := true.B }
    if (variant != "cover") {
      when(p.capture) { assert(age === 3.U) }
      when(longCount > bytes.U) { assert(p.reject) }
      when(previousRejected) {
        assert(p.tail === previousTail)
        when(!previousEnd) { assert(p.reject) }
        when(previousEnd) { assert(p.speculative === p.tail) }
      }
      if (sparse) {
        val tag = RegNext(RegNext(RegNext(p.head)))
        when(age === 3.U && cadence.enable) { assert(tag === p.head) }
      }
    } else {
      cover(wrappedAbort && end && !d.receiveError && !d.nak && longCount =/= 0.U)
    }
  }
}

/** Actual shared ResetRelease; both raw resets may reassert arbitrarily.
  * Root reset controls cadence; transport reset controls only the byte epoch.
  */
class UsbPacketEpochFormal(role: String, variant: String, bytes: Int, sparse: Boolean = false) extends RawModule {
  val clock = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val transportReset_n = IO(Input(Bool()))
  val data = IO(Input(UInt(8.W))); val operation = IO(Input(UInt(2.W)))
  val choose = IO(Input(Bool())); val push = IO(Input(Bool())); val ready = IO(Input(Bool()))
  val forgotten = if (sparse) Some(IO(Input(UInt(8.W)))) else None
  val release = Module(new ResetRelease)
  release.clk := clock; release.reset_n := reset_n && transportReset_n
  val pendingWrite = Wire(Bool()); val stalled = Wire(Bool())
  if (role == "in") {
    val subject = Module(new UsbInEpochSubject(variant, bytes, sparse))
    subject.forgotten.foreach(_ := forgotten.get)
    subject.clock := clock; subject.reset_n := release.released; subject.cadenceReset_n := reset_n
    subject.data := data; subject.operation := operation; subject.choose := choose; subject.push := push
    pendingWrite := subject.pendingWrite
    stalled := subject.stalled
  } else {
    val subject = Module(new UsbOutEpochSubject(variant, bytes, sparse))
    subject.forgotten.foreach(_ := forgotten.get)
    subject.clock := clock; subject.reset_n := release.released; subject.cadenceReset_n := reset_n
    subject.data := data; subject.operation := operation; subject.choose := choose; subject.ready := ready
    pendingWrite := subject.pendingWrite
    stalled := subject.stalled
  }
  withClockAndReset(clock, (!reset_n).asAsyncReset) {
    val phase = RegInit(0.U(2.W)); phase := phase + 1.U
    val previous = RegNext(release.released, false.B)
    val releasedOnce = RegInit(false.B); when(release.released) { releasedOnce := true.B }
    val resetAgain = RegInit(false.B); when(releasedOnce && !release.released) { resetAgain := true.B }
    val priorPending = RegNext(pendingWrite, false.B)
    val priorStalled = RegNext(stalled, false.B)
    if (variant == "cover") {
      for (p <- 0 until 4) { cover(release.released && !previous && phase === p.U) }
      cover(resetAgain && release.released)
      cover(priorPending && !transportReset_n)
      cover(priorStalled && !transportReset_n)
    }
  }
}

object EmitUsbPacketEpoch {
  def main(args: Array[String]): Unit = {
    require(args.length == 3 || args.length == 4)
    val root = Paths.get(args(0)).toAbsolutePath.normalize
    require(root.startsWith(Paths.get("build").toAbsolutePath.normalize))
    val role = args(1); require(Set("in", "out").contains(role))
    val bytes = args(2).toInt; require(Set(8, 16).contains(bytes))
    val sparse = args.length == 4 && args(3) == "sparse"
    require(args.length == 3 || Set("real", "sparse").contains(args(3)))
    for (variant <- (if (sparse) Seq("correct") else Seq("correct", "cover"))) {
      val dir = root.resolve(variant); Files.createDirectories(dir)
      ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new UsbPacketEpochFormal(role, variant, bytes, sparse)),
        Array("--target-dir", dir.toString),
        Array("--disable-all-randomization", "--verification-flavor=immediate", "--lower-to-core", "-strip-debug-info"))
    }
  }
}
