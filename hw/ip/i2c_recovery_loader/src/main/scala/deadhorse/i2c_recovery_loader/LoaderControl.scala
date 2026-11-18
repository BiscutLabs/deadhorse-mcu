// SPDX-License-Identifier: Apache-2.0
// Host-command and Stored transitions adapted from RISCay ClockedControl.
package deadhorse.i2c_recovery_loader

import chisel3._
import chisel3.util._

class LoaderControl(programBytes: Int, workingBytes: Int) extends RawModule {
  require(programBytes >= 4 && programBytes % 4 == 0)
  require(workingBytes >= 4 && workingBytes % 4 == 0)
  val clk = IO(Input(Clock()))
  val por_n = IO(Input(Bool()))
  val reset_n = IO(Input(Bool()))
  val frame = IO(Input(Valid(new HostFrame)))
  val frameReset = IO(Input(Bool()))
  val halted = IO(Input(Bool()))
  val memValid = IO(Output(Bool()))
  val memReady = IO(Input(Bool()))
  val memDone = IO(Input(Bool()))
  val memOffset = IO(Output(UInt(32.W)))
  val memWord = IO(Output(UInt(32.W)))
  val entry = IO(Output(UInt(32.W)))
  val programmed = IO(Output(Bool()))
  val locked = IO(Output(Bool()))
  val start = IO(Output(Bool()))
  val busy = IO(Output(Bool()))
  val wake = IO(Output(Bool()))
  val received = IO(Output(UInt(32.W)))
  val mode = IO(Output(UInt(3.W)))
  val canProgram = IO(Output(Bool()))
  val error = IO(Output(UInt(8.W)))
  val imageId = IO(Output(UInt(32.W)))
  val selector = IO(Output(UInt(24.W)))

  protected def lockResetN(value: Bool): Bool = value
  protected def accountedBytes(value: UInt): UInt = value
  protected def formalRange(count: UInt, length: UInt, pending: Bool, started: Bool): Unit = ()
  // The domain reset controller asserts reset_n for every whole-MCU reset,
  // including POR/brownout. por_n is its separate cold-only output.
  private val setLock = WireDefault(false.B)
  withClockAndReset(clk, (!lockResetN(por_n)).asAsyncReset) {
    val lock = RegInit(false.B)
    when(reset_n && setLock) { lock := true.B }
    locked := lock
  }

  withClockAndReset(clk, (!reset_n).asAsyncReset) {
    val idle :: crcStep :: request :: outstanding :: Nil = Enum(4)
    val phase = RegInit(idle)
    val completionHeld = RegInit(false.B)
    val validImage = RegInit(false.B)
    val currentMode = RegInit(0.U(3.W))
    val length = RegInit(0.U(log2Ceil(programBytes + 1).W))
    val count = RegInit(0.U(log2Ceil(programBytes + 1).W))
    val imageEntry = RegInit(0.U(log2Ceil(programBytes).W))
    val image = RegInit(0.U(32.W))
    val selected = RegInit(0.U(24.W))
    val lastError = RegInit(0.U(4.W))
    val expectedCrc = Reg(UInt(32.W))
    val crc = RegInit("hffffffff".U(32.W))
    val candidate = Reg(UInt(32.W))
    val crcBit = Reg(UInt(5.W))
    val word = Reg(UInt(32.W))
    val started = RegInit(false.B)
    val startPulse = RegInit(false.B)
    val wakePulse = RegInit(false.B)
    startPulse := false.B
    wakePulse := false.B

    val pending = phase =/= idle
    formalRange(count, length, pending, started)
    val writable = !locked && !started && !pending
    received := count
    memOffset := count
    memWord := word
    memValid := phase === request
    busy := pending
    entry := imageEntry
    programmed := validImage
    mode := currentMode
    canProgram := writable
    start := startPulse
    wake := wakePulse
    selector := selected
    error := lastError
    imageId := image

    // Reflected CRC32 over a little-endian word. Finish the candidate before
    // offering the memory request, then publish only on the matching Stored.
    when(phase === crcStep) {
      candidate := (candidate >> 1) ^ Mux(candidate(0), "hedb88320".U, 0.U)
      crcBit := crcBit - 1.U
      when(crcBit === 0.U) { phase := request }
    }
    when(phase === request && memReady) { phase := outstanding }
    when(phase === outstanding && memDone) { completionHeld := true.B }
    when(phase === outstanding && (memDone || completionHeld) && !frame.valid) {
      count := accountedBytes(count + 4.U)
      crc := candidate
      completionHeld := false.B
      phase := idle
    }

    val bytes = frame.bits.bytes
    def parameter(i: Int): UInt = Cat((0 until 4).reverse.map(j => bytes(1 + 4*i + j)))
    val opcode = bytes(0)
    val lengths = Seq(4,33,9,1,1,1,1,5,1,1,1)
    val wellFormed = !frame.bits.overflow && lengths.indices.map(i =>
      opcode === i.U && frame.bits.length === lengths(i).U).reduce(_ || _)
    val size = parameter(0)
    val offset = parameter(1)
    // Both fields arrive as unsigned 32-bit values. Reject high bits before
    // comparing bounded, aligned word indices. This avoids a 32-bit
    // variable comparator on the BEGIN-to-metadata path.
    val indexBits = length.getWidth
    val inRange = !(size >> indexBits).orR && !(offset >> indexBits).orR
    val sizeWords = size(indexBits - 1, 2)
    val entryWord = offset(indexBits - 1, 2)
    val legalRange = inRange && sizeWords <= (programBytes / 4).U &&
      entryWord < sizeWords && !size(1,0).orR && !offset(1,0).orR
    val compatible = parameter(3) === "h00010000".U && parameter(4) <= workingBytes.U &&
      parameter(5) === 0.U && parameter(6) === 0.U
    when(frame.valid) {
      when(!wellFormed) { lastError := 1.U }
        .elsewhen(opcode === 0.U) { selected := Cat(bytes(1), bytes(2), bytes(3)) }
        .elsewhen(frameReset || (pending && opcode <= 6.U)) { lastError := 3.U }
        .otherwise {
          lastError := 0.U
          switch(opcode) {
            is(1.U) {
              when(!writable) { lastError := Mux(locked, 2.U, 3.U) }
                .elsewhen(!legalRange) { lastError := 4.U }
                .elsewhen(!compatible) { lastError := 5.U }
                .otherwise {
                  currentMode := 1.U
                  validImage := false.B
                  count := 0.U
                  crc := "hffffffff".U
                  length := size
                  imageEntry := offset
                  expectedCrc := parameter(2)
                  image := parameter(7)
                }
            }
            is(2.U) {
              when(!writable) { lastError := Mux(locked, 2.U, 3.U) }
                .elsewhen(currentMode =/= 1.U) { lastError := 6.U }
                .elsewhen(size =/= count || count >= length) { lastError := 4.U }
                .otherwise {
                  word := parameter(1)
                  candidate := crc ^ parameter(1)
                  crcBit := 31.U
                  phase := crcStep
                }
            }
            is(3.U) {
              when(!writable || currentMode =/= 1.U) { lastError := Mux(locked, 2.U, 6.U) }
                .elsewhen(count =/= length) { lastError := 7.U }
                .elsewhen((~crc).asUInt =/= expectedCrc) { lastError := 8.U }
                .otherwise { validImage := true.B; currentMode := 2.U }
            }
            is(4.U, 5.U, 6.U) {
              when(!validImage || (started && opcode =/= 4.U)) { lastError := 6.U }
                .otherwise {
                  setLock := opcode === 4.U || opcode === 6.U
                  when(opcode =/= 4.U) {
                    started := true.B
                    startPulse := true.B
                    currentMode := 3.U
                  }
                }
            }
            is(7.U) { lastError := 4.U }
            is(8.U) { wakePulse := true.B }
            is(9.U, 10.U) { lastError := 5.U }
          }
        }
    }.elsewhen(halted && started) { currentMode := 4.U }
  }
}
