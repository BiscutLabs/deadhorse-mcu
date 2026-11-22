package deadhorse.top

import chisel3._
import chisel3.util._

/** A child fabric's observable epoch must drain before its parent can unpoison.
  * Waiting covers captured work, isolation covers orphaned endpoint work, and
  * the edge handshakes close the registered waiting signal's entry/exit gaps.
  */
class SocNestedDrain extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val request=IO(Input(Bool()));val grant=IO(Input(Bool()));val response=IO(Input(Bool()))
  val waiting=IO(Input(Bool()));val isolated=IO(Input(Bool()))
  val targetRequest=IO(Input(Bool()));val targetResponse=IO(Input(Bool()))
  val quiescent=IO(Output(Bool()))
  protected def acknowledgement(value: Bool): Bool=value
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val activity=waiting || isolated || grant || response || targetRequest || targetResponse
    quiescent:=acknowledgement(RegNext(!request && !activity,false.B))
    // A new external offer can rise before the registered quiet bit clears.
    // It must clear at the edge that can create a child grant or dispatch.
    assert(!quiescent || !activity)
  }
}
