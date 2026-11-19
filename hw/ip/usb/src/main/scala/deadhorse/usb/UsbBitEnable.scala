package deadhorse.usb

import chisel3._

/** One protocol edge per four sample edges, with a reset-defined phase. */
class UsbBitEnable extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val enable=IO(Output(Bool()))
  val preEnable=IO(Output(Bool()))
  protected def pulse(count: UInt): Bool=count===3.U
  protected def prePulse(count: UInt): Bool=count===2.U
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val count=RegInit(0.U(2.W))
    count:=count+1.U;enable:=RegNext(pulse(count),false.B)
    preEnable:=RegNext(prePulse(count),false.B)
  }
}
