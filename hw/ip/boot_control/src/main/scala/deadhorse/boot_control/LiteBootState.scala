package deadhorse.boot_control

import chisel3._

/** Performance-controlled lite reset, with a precise-boundary drain before hold.
  * The service reset clears commands, not a surviving application's release.
  */
class LiteBootState extends RawModule {
  val clk=IO(Input(Clock()));val epochReset_n=IO(Input(Bool()));val serviceReset_n=IO(Input(Bool()))
  val releaseCommand=IO(Input(Bool()));val releaseKey=IO(Input(Bool()))
  val holdCommand=IO(Input(Bool()));val holdKey=IO(Input(Bool()))
  val quiet=IO(Input(Bool()));val debugOwned=IO(Input(Bool()))
  val held=IO(Output(Bool()));val released=IO(Output(Bool()));val draining=IO(Output(Bool()))
  val error=IO(Output(Bool()))
  protected def drainComplete(quiet: Bool): Bool=quiet
  withClockAndReset(clk,(!epochReset_n).asAsyncReset) {
    val running=RegInit(false.B);val stopping=RegInit(false.B)
    held:= !running && !stopping;released:=running;draining:=stopping
    val releaseOk=releaseKey && !running && !stopping && !debugOwned && !holdCommand
    val holdOk=holdKey && !debugOwned && !releaseCommand
    when(serviceReset_n && releaseCommand && releaseOk) {running:=true.B}
    when(serviceReset_n && holdCommand && holdOk && running) {stopping:=true.B}
    when(stopping && drainComplete(quiet)) {running:=false.B;stopping:=false.B}
    error:=withReset((!(epochReset_n && serviceReset_n)).asAsyncReset) {
      RegNext(serviceReset_n && (releaseCommand && !releaseOk || holdCommand && !holdOk),false.B)
    }
  }
}
