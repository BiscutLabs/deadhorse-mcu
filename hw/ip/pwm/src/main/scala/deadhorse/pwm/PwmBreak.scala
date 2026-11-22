package deadhorse.pwm
import chisel3._

/** Conventional output-disable acknowledgment, independent of waveform state. */
class PwmBreak extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val idle=IO(Input(Bool()));val epochReady=IO(Input(Bool()));val stop=IO(Input(UInt(9.W)))
  val ready=IO(Output(Bool()));val permit=IO(Output(UInt(9.W)))
  protected def acknowledged(v: UInt): UInt=v
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val idleSeen=RegInit(false.B);val allowed=RegInit(0.U(9.W))
    when(!epochReady) {idleSeen:=false.B}.elsewhen(idle) {idleSeen:=true.B}
    when(idleSeen && epochReady) {allowed:=acknowledged(allowed | stop)}
    ready:=idleSeen;permit:=allowed
  }
}
