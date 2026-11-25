package deadhorse.lib

import chisel3._

/** Asynchronous assertion event flip-flop, followed by the shared synchronizer.
  * An input must return inactive until armed before the next distinct event.
  * Pulses while pending coalesce; physical minimum pulse width is a pad/cell
  * contract (PLAN05 initially assumes 1 us), not a digital proof result.
  */
class CdcPulseCapture extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val input=IO(Input(Bool()));val enable=IO(Input(Bool()));val falling=IO(Input(Bool()))
  val clear=IO(Input(Bool()));val pending=IO(Output(Bool()));val armed=IO(Output(Bool()))
  protected def captureInput(value: Bool): Bool=value
  protected def acceptedClear(command: Bool,seen: Bool): Bool=command && seen
  val level=Module(new CdcSync(1));level.clk:=clk;level.reset_n:=reset_n
  level.in:=(input ^ falling).asUInt
  val ready=withClockAndReset(clk,(!reset_n).asAsyncReset) {RegInit(false.B)}
  val event=captureInput((input ^ falling) && ready && enable)
  val clearSeen=WireDefault(false.B)
  // The reset-to-one cell is the capture element, not an asynchronous latch.
  // Startup suppresses its reset value until it has cleared and synchronized.
  val captured=withClockAndReset(clk,(event || !reset_n).asAsyncReset) {
    val flag=RegInit(true.B)
    when(clearSeen || !ready || !enable) {flag:=false.B}
    flag
  }
  val sync=Module(new CdcSync(1));sync.clk:=clk;sync.reset_n:=reset_n;sync.in:=captured.asUInt
  // A clear of an idle status cannot erase a just-arrived, not-yet-visible pulse.
  clearSeen:=acceptedClear(clear,sync.out.asBool)
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    // Wait through the initial capture/synchronizer reset pipeline before arm.
    val settling=RegInit(0.U(3.W))
    when(!enable) {ready:=false.B;settling:=0.U}
      .elsewhen(!ready) {
        when(settling=/=7.U) {settling:=settling+1.U}
        when(settling===7.U && !level.out.asBool && !sync.out.asBool) {ready:=true.B}
      }
    pending:=sync.out.asBool && ready && enable
    armed:=ready && enable && !sync.out.asBool && !level.out.asBool && !clear
  }
}
