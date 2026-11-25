package deadhorse.boot_control

import chisel3._

/** Reset metadata only; never grants program access or releases either hart. */
class BootResetContext extends RawModule {
  val clk=IO(Input(Clock()));val epochReset_n=IO(Input(Bool()))
  val warmHold=IO(Input(Bool()))
  val warmReleasePending=IO(Input(Bool()))
  val commit=IO(Input(Bool()));val commitKey=IO(Input(Bool()))
  val freshWarmReset=IO(Output(Bool()));val contextReady=IO(Output(Bool()))
  val error=IO(Output(Bool()))
  protected def initialHold: Boolean=true
  protected def validCommit(key: Bool): Bool=key
  withClockAndReset(clk,(!epochReset_n).asAsyncReset) {
    val previousHold=RegInit(initialHold.B)
    val fresh=RegInit(false.B);val ready=RegInit(false.B);val bad=RegInit(false.B)
    // Arm on the qualified release edge itself. Waiting to sample its output
    // one edge later loses a new pin pulse with the AON clock then stopped.
    previousHold:=warmHold && !warmReleasePending
    when(warmHold && !previousHold){fresh:=true.B}
    bad:=commit && !validCommit(commitKey)
    when(commit && validCommit(commitKey)){ready:=true.B}
    freshWarmReset:=fresh;contextReady:=ready;error:=bad
  }
}
