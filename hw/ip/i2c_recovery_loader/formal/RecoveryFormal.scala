package deadhorse.i2c_recovery_loader

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files, Paths}
import java.util.zip.CRC32

/** The mutations alter a production update or reset path. */
class WarmUnlockFault extends LoaderControl(2048, 1024) {
  override protected def lockResetN(coldReleased: Bool): Bool = coldReleased && reset_n
}

class DoubleCountFault extends LoaderControl(2048, 1024) {
  override protected def accountedBytes(next: UInt): UInt = next + 4.U
}

/** Additional assertions about real storage, proved alongside the port
  * properties. These make the full-capacity range obligation inductive.
  */
class RangeCheckedControl extends LoaderControl(2048, 1024) {
  override protected def formalRange(count: UInt, length: UInt, pending: Bool, started: Bool): Unit = {
    assert(count <= length && length <= 2048.U && count(1, 0) === 0.U &&
      length(1, 0) === 0.U &&
      (mode =/= 1.U || (!started && !locked && !programmed)) &&
      (!pending || (count < length && mode === 1.U)))
  }
}

/** All observations are on the control's frame, memory, reset and status ports.
  * Safety uses unconstrained completed frames. Concrete witnesses and the
  * bounded accounting check drive one upload at those same ports.
  */
class RecoveryFormal(role: String, variant: String) extends RawModule {
  val clock = IO(Input(Clock()))
  val por_n = IO(Input(Bool()))
  val warmReleased = IO(Input(Bool()))
  val frame = IO(Input(Valid(new HostFrame)))
  val interrupted = IO(Input(Bool()))
  val halted = IO(Input(Bool()))
  val ready = IO(Input(Bool()))
  val done = IO(Input(Bool()))
  val choice = IO(Input(UInt(3.W)))

  val dut = Module(if (role == "safety" && variant == "correct") new RangeCheckedControl
    else if (variant != "corrupt") new LoaderControl(2048, 1024)
    else if (role == "safety") new WarmUnlockFault
    else new DoubleCountFault)
  dut.clk := clock
  dut.por_n := por_n
  dut.reset_n := warmReleased && por_n
  dut.frame := frame
  dut.frameReset := interrupted
  dut.halted := halted
  dut.memReady := ready
  dut.memDone := done

  val scripted = role == "accounting" || variant != "correct"
  withClockAndReset(clock, (!por_n).asAsyncReset) {
    val age = RegInit(0.U(7.W))
    val selected = RegInit(0.U(3.W))
    when (age === 0.U) { selected := choice }
    when (age < 90.U) { age := age + 1.U }

    val patterns = Seq(0x807f01feL, 0x01234567L)
    def checksum(word: Long): Long = {
      val crc = new CRC32
      (0 until 4).foreach(i => crc.update(((word >>> (8 * i)) & 255).toInt))
      crc.getValue
    }
    val payload = Mux(selected(0), patterns(1).U(32.W), patterns(0).U(32.W))
    val digest = Mux(selected(0), checksum(patterns(1)).U(32.W), checksum(patterns(0)).U(32.W))
    val completion = 54.U +& selected(2, 1)
    if (scripted) {
      dut.reset_n := por_n && !(age >= 72.U && age < 75.U)
      dut.halted := false.B
      dut.frameReset := false.B
      dut.memReady := age >= 48.U
      dut.memDone := age === 8.U || age === 17.U || age === completion || age === 62.U
      dut.frame := 0.U.asTypeOf(dut.frame)
      def command(op: Int, length: Int, words: UInt*): Unit = {
        dut.frame.valid := true.B
        dut.frame.bits.length := length.U
        dut.frame.bits.bytes(0) := op.U
        for ((word, index) <- words.zipWithIndex; byte <- 0 until 4) {
          dut.frame.bits.bytes(1 + index * 4 + byte) := word.pad(32)(byte * 8 + 7, byte * 8)
        }
      }
      def begin(): Unit = command(1, 33, 4.U, 0.U, digest, "h10000".U, 0.U, 0.U, 0.U, 1.U)
      when (age === 1.U || age === 77.U) { begin() }
      when (age === 3.U) { command(2, 8, 0.U, payload) }
      when (age === 6.U) { command(2, 9, "h10000".U, payload) }
      when (age === 12.U || age === 79.U) { command(2, 9, 0.U, payload) }
      when (age === completion) { command(0, 4) }
      when (age === 63.U) { command(3, 1) }
      when (age === 67.U) { command(6, 1) }
    }

    val active = dut.reset_n && por_n
    val previouslyLocked = RegNext(dut.locked, false.B)
    val commandStart = dut.frame.valid && !dut.frame.bits.overflow &&
      dut.frame.bits.length === 1.U &&
      (dut.frame.bits.bytes(0) === 5.U || dut.frame.bits.bytes(0) === 6.U)
    val allowedStart = RegNext(active && dut.programmed && commandStart && !dut.frameReset, false.B)
    val admissibleWrite = dut.frame.valid && !dut.frame.bits.overflow && !dut.frameReset &&
      dut.frame.bits.length === 9.U && dut.frame.bits.bytes(0) === 2.U &&
      Cat(dut.frame.bits.bytes.slice(1, 5).reverse) === dut.received &&
      dut.mode === 1.U && !dut.locked && !dut.programmed
    // One grant may consume each write authorization. An aborted authorization
    // is discarded on reset. This monitor deliberately uses no DUT state bits.
    val credit = withReset((!active).asAsyncReset) {
      val pending = RegInit(false.B)
      when (admissibleWrite) { pending := true.B }
      when (dut.memValid && dut.memReady) { pending := false.B }
      pending
    }
    val safety = (!previouslyLocked || dut.locked) &&
      (!dut.start || (active && dut.programmed && allowedStart)) &&
      (!dut.memValid || (active && !dut.locked && !dut.programmed &&
        dut.mode === 1.U && credit && dut.memOffset === dut.received &&
        dut.memOffset < 2048.U && dut.memOffset(1, 0) === 0.U))

    if (role == "safety") {
      if (variant == "cover") {
        cover(dut.memValid && dut.memReady)
        cover(dut.start && dut.programmed && dut.locked)
        cover(age === 81.U && dut.locked && !dut.programmed && !dut.memValid)
      } else { assert(safety) }
    } else {
      val writes = RegInit(0.U(3.W))
      when (dut.memValid && dut.memReady) { writes := writes + 1.U }
      val expectedCount = Mux(age > completion +& 1.U && age < 72.U, 4.U, 0.U)
      // After the SELECT at completion, one free edge publishes Stored.
      val accounting =
        (dut.received === expectedCount) &&
        (age >= 13.U || !dut.memValid) &&
        (age =/= 48.U || dut.memValid) &&
        (!dut.memValid || (dut.memWord === payload && dut.memOffset === 0.U)) &&
        (age < 49.U || writes === 1.U) &&
        (age =/= 65.U || (dut.programmed && dut.mode === 2.U)) &&
        (age =/= 68.U || (dut.programmed && dut.start && dut.locked)) &&
        (age < 73.U || (dut.locked && !dut.programmed && dut.mode === 0.U && !dut.memValid))
      if (variant == "cover") {
        cover(age === 85.U && writes === 1.U && dut.locked && selected === 0.U)
        cover(age === 85.U && writes === 1.U && dut.locked && selected === 7.U)
      } else { assert(accounting) }
    }
  }
}

object EmitRecoveryFormal {
  def main(args: Array[String]): Unit = {
    require(args.length == 1, "EmitRecoveryFormal build/<output>")
    val root = Paths.get(args(0)).toAbsolutePath.normalize
    require(root.startsWith(Paths.get("build").toAbsolutePath.normalize))
    for (role <- Seq("safety", "accounting"); variant <- Seq("correct", "corrupt", "cover")) {
      val dir = root.resolve(role).resolve("emit").resolve(variant)
      Files.createDirectories(dir)
      ChiselStage.emitSystemVerilogFile(
        chisel3.layer.elideBlocks(new RecoveryFormal(role, variant)),
        Array("--target-dir", dir.toString),
        Array("--disable-all-randomization", "--verification-flavor=immediate", "--lower-to-core", "-strip-debug-info"))
    }
  }
}
