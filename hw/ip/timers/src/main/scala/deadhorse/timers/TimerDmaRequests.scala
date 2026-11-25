package deadhorse.timers
import chisel3._

/** One outstanding event per channel; simultaneous service and event replaces it. */
class TimerDmaRequests extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val events=IO(Input(UInt(9.W)));val mask=IO(Input(UInt(9.W)));val acknowledge=IO(Input(UInt(9.W)))
  val request=IO(Output(UInt(9.W)));val overrun=IO(Output(UInt(9.W)))
  protected def requestValue(v: UInt): UInt=v
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val pending=RegInit(0.U(9.W))
    pending:=requestValue(((pending & ~acknowledge) | events) & mask)
    request:=pending
    overrun:=RegNext(events & pending & ~acknowledge & mask,0.U)
  }
}
