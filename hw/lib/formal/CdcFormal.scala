package deadhorse.lib

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

class CdcCorruptRead(width: Int, depth: Int) extends CdcRead(width, depth) {
  override protected def capture(value: UInt): UInt = value ^ 1.U
}
class CdcCorruptFifo(width: Int, depth: Int) extends CdcFifo(width, depth) {
  override protected def makeReader(): CdcRead = new CdcCorruptRead(width, depth)
}
class CdcBinaryWrite(depth: Int) extends CdcWrite(8, depth) {
  override protected def encode(value: UInt): UInt = value
}
class CdcEarlyRelease extends ResetRelease {
  override protected def qualified(first: Bool, second: Bool): Bool = first
}

/** Independent sequence-number FIFO oracle in the two real clock domains.
  * No DUT pointer, memory or synchronizer state is used by the checker.
  */
class CdcFormal(width: Int, depth: Int, variant: String) extends RawModule {
  val observeClock = IO(Input(Clock())) // independent unconstrained observation clock
  val checking = IO(Output(Bool()))
  val wc = IO(Input(Clock())); val rc = IO(Input(Clock()))
  val wn = IO(Input(Bool())); val rn = IO(Input(Bool()))
  val push = IO(Input(Bool())); val data = IO(Input(UInt(width.W)))
  val pop = IO(Input(Bool()))
  def candidate: CdcFifo = if (variant == "corrupt") new CdcCorruptFifo(width, depth) else new CdcFifo(width, depth)
  val dut = Module(candidate)
  dut.writeClock := wc; dut.readClock := rc
  dut.writeReset_n := wn; dut.readReset_n := rn
  dut.push := push; dut.in := data; dut.pop := pop
  val reset = (!(wn && rn)).asAsyncReset
  val countWidth = log2Ceil(depth) + 1
  val enqueued = withClockAndReset(wc, reset) { RegInit(0.U(countWidth.W)) }
  val dequeued = withClockAndReset(rc, reset) { RegInit(0.U(countWidth.W)) }
  val expected = withClockAndReset(wc, reset) { Reg(Vec(depth, UInt(width.W))) }
  val occupancy = enqueued - dequeued
  val put = push && dut.ready
  val take = pop && dut.valid
  withClockAndReset(wc, reset) {
    when(put) {
      expected(enqueued(log2Ceil(depth)-1, 0)) := data
      enqueued := enqueued + 1.U
    }
    val priorPut = RegNext(put, false.B)
    val waitForSpace = RegInit(0.U(4.W))
    val waitForIdle = RegInit(0.U(4.W))
    when(occupancy < depth.U && !dut.ready) { waitForSpace := waitForSpace + 1.U }
      .otherwise { waitForSpace := 0.U }
    when(occupancy === 0.U && dut.writePending && !put) { waitForIdle := waitForIdle + 1.U }
      .otherwise { waitForIdle := 0.U }
    if (variant != "cover") {
      assert(occupancy <= depth.U)
      assert(!put || occupancy < depth.U)
      assert(!priorPut || dut.writePending)
      assert(occupancy === 0.U || dut.writePending)
      assert(waitForSpace < 8.U)
      assert(waitForIdle < 8.U)
    } else {
      cover(put && enqueued === (2*depth-1).U)
      cover(occupancy === depth.U && !dut.ready)
    }
  }
  withClockAndReset(rc, reset) {
    when(take) { dequeued := dequeued + 1.U }
    val wasHeld = RegNext(dut.valid && !pop, false.B)
    val priorData = RegNext(dut.out)
    // Two reset-release edges, two pointer-synchronizer edges, head capture,
    // and observer sampling fit inside eight running receive-clock edges.
    val waitForHead = RegInit(0.U(4.W))
    when(occupancy === 0.U || dut.valid) { waitForHead := 0.U }
      .otherwise { waitForHead := waitForHead + 1.U }
    if (variant != "cover") {
      assert(!dut.valid || occupancy > 0.U)
      assert(!dut.valid || dut.out === expected(dequeued(log2Ceil(depth)-1, 0)))
      assert(!wasHeld || (dut.valid && dut.out === priorData))
      assert(waitForHead < 8.U)
    } else {
      cover(take && dequeued === (2*depth-1).U)
      cover(wasHeld && take)
    }
  }
  withClockAndReset(observeClock, false.B) {
    val history = RegNext(true.B)
    dontTouch(history)
    checking := history
    val oldOccupancy = RegNext(occupancy)
    val oldWc = RegNext(wc.asBool); val oldRc = RegNext(rc.asBool)
    val resetWithWork = Reg(Bool())
    val stoppedWork = Reg(Bool())
    when(!history) { resetWithWork := false.B; stoppedWork := false.B }
      .otherwise {
        when(!(wn && rn) && oldOccupancy > 0.U) { resetWithWork := true.B }
        when(dut.writePending && !rc.asBool && !oldRc) { stoppedWork := true.B }
      }
    if (variant != "cover") assert((wn && rn) || (!dut.ready && !dut.valid && !dut.writeUp && !dut.readUp))
    else {
      cover(history && resetWithWork && rn && wn && dut.valid && pop && rc.asBool && !oldRc)
      cover(history && stoppedWork && dut.valid && pop && rc.asBool && !oldRc)
      cover(history && !wn && rn && oldOccupancy > 0.U && !wc.asBool && !rc.asBool)
      cover(history && wn && !rn && oldOccupancy > 0.U && !wc.asBool && !rc.asBool)
      cover(history && wc.asBool && !oldWc && rc.asBool && !oldRc && put && take)
    }
  }
}

/** Public side ports prove registered Gray transitions and reset-release delay. */
class CdcSideFormal(depth: Int, variant: String) extends RawModule {
  val clock = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val push = IO(Input(Bool())); val pop = IO(Input(Bool()))
  val otherGray = IO(Input(UInt((log2Ceil(depth)+1).W)))
  val data = IO(Input(UInt(8.W)))
  def writer: CdcWrite = if (variant == "bad_gray") new CdcBinaryWrite(depth) else new CdcWrite(8, depth)
  def resetter: ResetRelease = if (variant == "early_release") new CdcEarlyRelease else new ResetRelease
  val w = Module(writer); val r = Module(new CdcRead(8, depth))
  val release = Module(resetter)
  w.clk := clock; r.clk := clock; release.clk := clock
  w.reset_n := reset_n; r.reset_n := reset_n; release.reset_n := reset_n
  w.push := push; w.data := data; w.readGray := otherGray
  r.pop := pop; r.writeGray := otherGray; r.words := VecInit(Seq.fill(depth)(data))
  withClockAndReset(clock, (!reset_n).asAsyncReset) {
    val history = RegNext(true.B, false.B)
    val oldW = Reg(UInt((log2Ceil(depth)+1).W)); val oldR = Reg(UInt((log2Ceil(depth)+1).W))
    oldW := w.writeGray; oldR := r.readGray
    val pushed = RegNext(push && w.ready, false.B)
    val popped = RegNext(pop && r.valid, false.B)
    val edges = RegInit(0.U(2.W))
    when(edges =/= 2.U) { edges := edges + 1.U }
    if (variant == "cover") {
      cover(history && pushed && popped)
      cover(release.released)
    } else {
      when(history) {
        assert(PopCount(w.writeGray ^ oldW) === pushed.asUInt)
        assert(PopCount(r.readGray ^ oldR) === popped.asUInt)
      }
      assert(release.released === (edges === 2.U))
    }
  }
}

object EmitCdcFormal {
  def main(args: Array[String]): Unit = {
    require(args.length == 3, "EmitCdcFormal width depth build/output")
    val root = Paths.get(args(2)).toAbsolutePath.normalize
    require(root.startsWith(Paths.get("build").toAbsolutePath.normalize))
    for (variant <- Seq("correct", "corrupt", "cover")) {
      val dir = root.resolve(variant); Files.createDirectories(dir)
      ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new CdcFormal(args(0).toInt, args(1).toInt, variant)),
        Array("--target-dir", dir.toString),
        Array("--disable-all-randomization", "--verification-flavor=immediate", "--lower-to-core", "-strip-debug-info"))
    }
    for (variant <- Seq("correct", "bad_gray", "early_release", "cover")) {
      val dir = root.resolve("side_" + variant); Files.createDirectories(dir)
      ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new CdcSideFormal(args(1).toInt, variant)),
        Array("--target-dir", dir.toString),
        Array("--disable-all-randomization", "--verification-flavor=immediate", "--lower-to-core", "-strip-debug-info"))
    }
  }
}
