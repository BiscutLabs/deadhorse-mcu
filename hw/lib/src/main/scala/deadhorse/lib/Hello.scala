package deadhorse.lib

import chisel3._

/** One registered byte successor; reset assertion does not require a clock. */
class Hello extends RawModule {
  val clock = IO(Input(Clock()))
  val reset_n = IO(Input(Bool()))
  val in = IO(Input(UInt(8.W)))
  val out = IO(Output(UInt(8.W)))

  protected def successor(value: UInt): UInt = value + 1.U
  protected def resetValue: Int = 0
  withClockAndReset(clock, (!reset_n).asAsyncReset) {
    val result = RegInit(resetValue.U(8.W))
    result := successor(in)
    out := result
  }
}
