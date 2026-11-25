package deadhorse.bus_bridge

import chisel3._

/** Registered four-phase grant for a bridge with no opposing direction.
  * This is admission only: FIFO readiness, epoch and owner checks stay in
  * their existing endpoints. The caller supplies its qualified domain reset.
  */
class LocalPermit extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val request=IO(Input(Bool()));val permit=IO(Output(Bool()))
  protected def sampled(request: Bool): Bool=request
  protected def initialPermit: Boolean=false
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    permit:=RegNext(sampled(request),initialPermit.B)
  }
}
