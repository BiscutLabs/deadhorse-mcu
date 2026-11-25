package deadhorse.boot_control
import chisel3._

/** Board strap stable through qualification. The data flop samples even under
  * reset; no client sees it before the reset-qualified freeze edge. */
class BootModeStrap extends RawModule {
  val clk=IO(Input(Clock()));val wholeReset_n=IO(Input(Bool()))
  val qualified=IO(Input(Bool()));val pad=IO(Input(Bool()))
  val value=IO(Output(Bool()));val frozen=IO(Output(Bool()))
  protected def heldValue(held: Bool,raw: Bool): Bool=held
  val locked=withClockAndReset(clk,(!wholeReset_n).asAsyncReset) {
    val q=RegInit(false.B);when(qualified) {q:=true.B};q
  }
  val sampled=withClockAndReset(clk,false.B) {
    val q=Reg(Bool());when(!locked) {q:=pad};q
  }
  frozen:=locked;value:=locked && heldValue(sampled,pad)
}
