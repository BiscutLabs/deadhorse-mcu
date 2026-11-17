package deadhorse.lib

import chisel3._
import chisel3.util._

/** The only reset-release primitive: asynchronous assert, two local edges out. */
class ResetRelease extends RawModule {
  protected def qualified(first: Bool, second: Bool): Bool = second
  val clk = IO(Input(Clock()))
  val reset_n = IO(Input(Bool()))
  val released = IO(Output(Bool()))
  withClockAndReset(clk, (!reset_n).asAsyncReset) {
    val first = RegInit(false.B)
    val second = RegInit(false.B)
    first := true.B
    second := first
    dontTouch(first); dontTouch(second)
    released := qualified(first, second)
  }
}

/** Use only for a stable single-bit level or a registered Gray-code pointer. */
class CdcSync(width: Int) extends RawModule {
  val clk = IO(Input(Clock()))
  val reset_n = IO(Input(Bool()))
  val in = IO(Input(UInt(width.W)))
  val out = IO(Output(UInt(width.W)))
  withClockAndReset(clk, (!reset_n).asAsyncReset) {
    val metastable = RegInit(0.U(width.W))
    val stable = RegInit(0.U(width.W))
    metastable := in
    stable := metastable
    dontTouch(metastable); dontTouch(stable)
    out := stable
  }
}

/** Write-clock half. Split into a real production module for local timing. */
class CdcWrite(width: Int, depth: Int) extends RawModule {
  protected def encode(value: UInt): UInt = (value >> 1) ^ value
  require(depth >= 2 && depth <= 32 && isPow2(depth))
  val bits = log2Ceil(depth)
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val push = IO(Input(Bool())); val data = IO(Input(UInt(width.W)))
  val ready = IO(Output(Bool())); val pending = IO(Output(Bool()))
  val readGray = IO(Input(UInt((bits + 1).W)))
  val writeGray = IO(Output(UInt((bits + 1).W)))
  val words = IO(Output(Vec(depth, UInt(width.W))))
  val sync = Module(new CdcSync(bits + 1))
  sync.clk := clk; sync.reset_n := reset_n; sync.in := readGray
  withClockAndReset(clk, (!reset_n).asAsyncReset) {
    val memory = Reg(Vec(depth, UInt(width.W)))
    val binary = RegInit(0.U((bits + 1).W))
    val gray = RegInit(0.U((bits + 1).W))
    val canPush = RegInit(false.B)
    val work = RegInit(false.B)
    val accept = push && canPush
    val next = binary + accept.asUInt
    val nextGray = encode(next)
    val fullCompare = sync.out ^ (BigInt(3) << (bits - 1)).U((bits + 1).W)
    when(accept) { memory(binary(bits - 1, 0)) := data }
    binary := next; gray := nextGray
    canPush := nextGray =/= fullCompare
    work := nextGray =/= sync.out
    ready := canPush; pending := work; writeGray := gray; words := memory
  }
}

/** Read-clock half. A registered head is included in logical FIFO capacity. */
class CdcRead(width: Int, depth: Int) extends RawModule {
  require(depth >= 2 && depth <= 32 && isPow2(depth))
  val bits = log2Ceil(depth)
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val pop = IO(Input(Bool())); val data = IO(Output(UInt(width.W)))
  val valid = IO(Output(Bool()))
  val writeGray = IO(Input(UInt((bits + 1).W)))
  val readGray = IO(Output(UInt((bits + 1).W)))
  val words = IO(Input(Vec(depth, UInt(width.W))))
  protected def capture(value: UInt): UInt = value
  val sync = Module(new CdcSync(bits + 1))
  sync.clk := clk; sync.reset_n := reset_n; sync.in := writeGray
  withClockAndReset(clk, (!reset_n).asAsyncReset) {
    val binary = RegInit(0.U((bits + 1).W))
    val gray = RegInit(0.U((bits + 1).W))
    val head = RegInit(0.U(width.W))
    val present = RegInit(false.B)
    when(present && pop) {
      val next = binary + 1.U
      binary := next; gray := (next >> 1) ^ next; present := false.B
    }
    when(!present && gray =/= sync.out) {
      head := capture(words(binary(bits - 1, 0))); present := true.B
    }
    valid := present; data := head; readGray := gray
  }
}

class CdcFifo(width: Int, depth: Int = 2) extends RawModule {
  protected def makeReader(): CdcRead = new CdcRead(width, depth)
  val writeClock = IO(Input(Clock())); val readClock = IO(Input(Clock()))
  val writeReset_n = IO(Input(Bool())); val readReset_n = IO(Input(Bool()))
  val push = IO(Input(Bool())); val in = IO(Input(UInt(width.W)))
  val ready = IO(Output(Bool())); val writePending = IO(Output(Bool()))
  val pop = IO(Input(Bool())); val out = IO(Output(UInt(width.W)))
  val valid = IO(Output(Bool()))
  val writeUp = IO(Output(Bool())); val readUp = IO(Output(Bool()))
  val commonReset_n = writeReset_n && readReset_n
  val wr = Module(new ResetRelease); val rd = Module(new ResetRelease)
  wr.clk := writeClock; rd.clk := readClock
  wr.reset_n := commonReset_n; rd.reset_n := commonReset_n
  val writer = Module(new CdcWrite(width, depth)); val reader = Module(makeReader())
  writer.clk := writeClock; writer.reset_n := wr.released
  reader.clk := readClock; reader.reset_n := rd.released
  writer.readGray := reader.readGray; reader.writeGray := writer.writeGray
  reader.words := writer.words
  writer.push := push; writer.data := in; reader.pop := pop
  ready := writer.ready; writePending := writer.pending
  valid := reader.valid; out := reader.data
  writeUp := wr.released; readUp := rd.released
}
