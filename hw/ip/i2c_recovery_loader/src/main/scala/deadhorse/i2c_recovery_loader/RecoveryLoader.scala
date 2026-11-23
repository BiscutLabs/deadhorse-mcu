// SPDX-License-Identifier: Apache-2.0
// Adapted from the pinned ClockedFabric read bank, memory and host dispatch.
package deadhorse.i2c_recovery_loader

import chisel3._
import chisel3.util._

class RecoveryLoader(programBytes: Int = 2048, workingBytes: Int = 1024,
                     idleCycles: Int = 262144, debugInterlock: Boolean=false) extends RawModule {
  val debugInhibit=if(debugInterlock) Some(IO(Input(Bool()))) else None
  val clk = IO(Input(Clock()))
  val por_n = IO(Input(Bool()))
  val reset_n = IO(Input(Bool()))
  val sclIn = IO(Input(Bool()))
  val sdaIn = IO(Input(Bool()))
  val sdaLow = IO(Output(Bool()))
  val memValid = IO(Output(Bool()))
  val memReady = IO(Input(Bool()))
  val memDone = IO(Input(Bool()))
  val memOffset = IO(Output(UInt(32.W)))
  val memWord = IO(Output(UInt(32.W)))
  val halted = IO(Input(Bool()))
  val resetReason = IO(Input(UInt(32.W)))
  val crashCount = IO(Input(UInt(32.W)))
  val start = IO(Output(Bool()))
  val entry = IO(Output(UInt(32.W)))
  val programmed = IO(Output(Bool()))
  val locked = IO(Output(Bool()))
  val busy = IO(Output(Bool()))
  val clockHold = IO(Output(Bool()))
  val wake = IO(Output(Bool()))
  protected def storeWord(value: UInt): UInt = value

  private val control = Module(new LoaderControl(programBytes, workingBytes))
  control.clk := clk
  control.por_n := por_n
  control.reset_n := reset_n
  control.halted := halted
  control.memReady := memReady
  control.memDone := memDone
  memOffset := control.memOffset
  memValid := control.memValid
  memWord := storeWord(control.memWord)
  start := control.start
  entry := control.entry
  programmed := control.programmed
  locked := control.locked
  busy := control.busy
  wake := control.wake

  withClockAndReset(clk, (!reset_n).asAsyncReset) {
    val target = Module(new ClockedI2cTarget(0x35, idleCycles))
    target.io.scl := sclIn
    target.io.sda := sdaIn
    target.io.applicationCancel := false.B // D37 has no CPU-only lite reset.
    control.frame := target.io.frame
    // T32 ownership cancellation uses the existing busy/error path. An already
    // accepted memory operation is unaffected; only new mutating frames cancel.
    val opcode=target.io.frame.bits.bytes(0)
    control.frameReset := target.io.frameReset ||
      (debugInhibit.getOrElse(false.B) && opcode>=1.U && opcode<=6.U)
    sdaLow := target.io.pullLow
    clockHold := RegNext(target.io.busy || control.busy || target.io.frame.valid, false.B)

    // Capture the first word's index along with the entire selected service.
    // Later changes at the device and loader ports cannot tear this read.
    val device = Seq("h00010000".U, 1.U, 1.U, programBytes.U, workingBytes.U,
      0.U, 0.U, resetReason, crashCount)
    val loader = Seq(control.mode, control.programmed, control.locked,
      control.canProgram, control.busy, control.error, control.imageId,
      control.received, 0.U)
    val service = control.selector(23, 8)
    val bank = Reg(Vec(9, UInt(32.W)))
    val supported = Reg(Bool())
    val first = Reg(UInt(8.W))
    when(target.io.readStart) {
      for (index <- device.indices) { bank(index) := Mux(service === 0.U, device(index), loader(index)) }
      supported := service === 0.U || service === 256.U
      first := control.selector(7, 0)
    }
    val wordIndex = target.io.wordIndex
    val address = first +& wordIndex
    val mask = VecInit((0 until 8).map(i => supported && first <= (8 - i).U)).asUInt
    val data = Mux(supported && address <= 8.U, bank(address(3, 0)), "hffffffff".U)
    // wordIndex advances before the final ACK fall where the target loads
    // its serializer. Register the lookup to isolate the SDA launch path.
    target.io.readWord := RegNext(Mux(wordIndex === 8.U, mask, data))
  }
}
