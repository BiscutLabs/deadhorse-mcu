package deadhorse.osc_ctrl

import chisel3._
import chisel3.util._
import deadhorse.lib._

/** Atomic sleep/mode transfers through the shared FIFO. Source pending remains
  * a clock hold until the main endpoint has consumed the complete payload. */
class OscSleepTransfer extends RawModule {
  protected def acknowledge(value: Bool): Bool=value
  val aon=IO(Input(Clock()));val main=IO(Input(Clock()))
  val aonReset_n=IO(Input(Bool()));val mainReset_n=IO(Input(Bool()))
  val requested=IO(Input(Bool()));val modes=IO(Input(UInt(6.W)))
  val applied=IO(Output(Bool()));val appliedModes=IO(Output(UInt(6.W)))
  val settled=IO(Output(Bool()))
  val fifo=Module(new CdcFifo(7))
  fifo.writeClock:=aon;fifo.readClock:=main
  fifo.writeReset_n:=aonReset_n;fifo.readReset_n:=mainReset_n
  // FIFO endpoint releases are synchronized independently to their clocks.
  // Either raw reset still asserts both endpoint resets asynchronously.
  withClockAndReset(aon,(!fifo.writeUp).asAsyncReset) {
    val last=RegInit(0.U(7.W));val desired=Cat(requested,modes)
    val push=fifo.ready && desired=/=last
    fifo.push:=push;fifo.in:=desired
    when(push) {last:=desired}
    // Read-pointer acknowledgement follows the main payload capture.
    settled:=acknowledge(RegNext(desired===last && !fifo.writePending && fifo.writeUp,false.B))
  }
  withClockAndReset(main,(!fifo.readUp).asAsyncReset) {
    val received=RegInit(0.U(7.W))
    when(fifo.valid) {received:=fifo.out}
    fifo.pop:=fifo.valid
    applied:=received(6);appliedModes:=received(5,0)
  }
}
