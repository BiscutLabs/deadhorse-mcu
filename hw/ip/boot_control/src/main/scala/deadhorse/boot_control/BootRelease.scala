package deadhorse.boot_control
import chisel3._

class BootRelease extends RawModule {
  val clk=IO(Input(Clock()));val epochReset_n=IO(Input(Bool()));val serviceReset_n=IO(Input(Bool()))
  val startAccepted=IO(Input(Bool()));val command=IO(Input(Bool()));val keyGood=IO(Input(Bool()))
  val bootSeen=IO(Output(Bool()));val released=IO(Output(Bool()));val error=IO(Output(Bool()))
  protected def eligible(seen: Bool,key: Bool): Bool=seen && key
  withClockAndReset(clk,(!epochReset_n).asAsyncReset) {
    val seen=RegInit(false.B);val open=RegInit(false.B)
    when(serviceReset_n && startAccepted) {seen:=true.B}
    when(serviceReset_n && command && eligible(seen,keyGood)) {open:=true.B}
    bootSeen:=seen;released:=open
    error:=withReset((!(epochReset_n && serviceReset_n)).asAsyncReset) {
      RegNext(command && (!seen || !keyGood),false.B)
    }
  }
}
