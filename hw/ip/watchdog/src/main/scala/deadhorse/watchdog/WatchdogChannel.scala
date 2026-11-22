// SPDX-License-Identifier: Apache-2.0
// Count/hold structure adapted from pinned RISCay ClockedWatchdog; see PROVENANCE.json.
package deadhorse.watchdog
import chisel3._
import chisel3.util._

class WatchdogChannel extends RawModule {
  val clk=IO(Input(Clock()));val por_n=IO(Input(Bool()));val reset_n=IO(Input(Bool()))
  val period=IO(Input(UInt(32.W)));val window=IO(Input(UInt(32.W)));val warning=IO(Input(UInt(32.W)))
  val start=IO(Input(Bool()));val feed=IO(Input(Bool()))
  val active=IO(Output(Bool()));val remaining=IO(Output(UInt(32.W)));val warn=IO(Output(Bool()))
  val resetHold=IO(Output(Bool()));val cause=IO(Output(Bool()));val crashes=IO(Output(UInt(32.W)))
  val error=IO(Output(Bool()))
  protected def earlyViolation(v: Bool): Bool=v
  protected def retainedReset: Bool=por_n
  protected def holdLength: UInt=4.U(3.W)
  val trip=WireDefault(false.B)
  withClockAndReset(clk,(!retainedReset).asAsyncReset) {
    val hold=RegInit(0.U(3.W));val reason=RegInit(false.B);val count=RegInit(0.U(32.W))
    when(hold=/=0.U) {hold:=hold-1.U}
    when(trip) {hold:=holdLength;reason:=true.B;when(!count.andR) {count:=count+1.U}}
    resetHold:=hold=/=0.U;cause:=reason;crashes:=count
  }
  withClockAndReset(clk,(!(por_n && reset_n)).asAsyncReset) {
    val running=RegInit(false.B);val left=RegInit(0.U(32.W))
    val limit=RegInit(0.U(32.W));val lastEarly=RegInit(0.U(32.W));val threshold=RegInit(0.U(32.W))
    val warningOut=RegInit(false.B);val bad=RegInit(false.B)
    val early=earlyViolation(feed && !start && left-1.U>lastEarly)
    trip:=reset_n && por_n && running && !resetHold && (left===1.U || early)
    bad:=false.B
    when(resetHold) {bad:=start || feed}
      .elsewhen(running) {
        bad:=start
        when(trip) {running:=false.B;left:=0.U;warningOut:=false.B}
          .elsewhen(feed && !start) {left:=limit;warningOut:=false.B}
          .otherwise {left:=left-1.U;warningOut:=threshold=/=0.U && left-1.U<=threshold}
      }.elsewhen(start && !feed && period=/=0.U && window<period && warning<period) {
        running:=true.B;left:=period;limit:=period;lastEarly:=period-window;threshold:=warning
        warningOut:=false.B
      }.otherwise {bad:=start || feed}
    active:=running;remaining:=left;warn:=warningOut;error:=bad
  }
}
