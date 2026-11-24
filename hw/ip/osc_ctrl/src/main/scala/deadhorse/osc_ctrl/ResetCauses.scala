package deadhorse.osc_ctrl

import chisel3._
import chisel3.util.Cat
import deadhorse.lib._

/** Held causes for T33, separate from the unchanged loader watchdog ABI.
  * Pin pulses are stretched by the shared async-assert release primitive.
  * POR/brownout classification uses the analog macro's held power-epoch flag. */
class ResetCauses extends RawModule {
  val clk=IO(Input(Clock()));val coldReset_n=IO(Input(Bool()))
  val externalReset_n=IO(Input(Bool()));val bypass=IO(Input(Bool()))
  val brownout=IO(Input(Bool()));val causes=IO(Output(UInt(3.W)))
  val cold=Module(new ResetRelease);cold.clk:=clk;cold.reset_n:=coldReset_n
  val pin=Module(new ResetRelease);pin.clk:=clk;pin.reset_n:=externalReset_n
  val brown=Module(new CdcSync(1));brown.clk:=clk;brown.reset_n:=cold.released;brown.in:=brownout.asUInt
  withClockAndReset(clk,(!cold.released).asAsyncReset) {
    val pinSeen=RegInit(false.B);val brownSeen=RegInit(false.B)
    when(!pin.released) {pinSeen:=true.B}
    when(brown.out.asBool && !bypass) {brownSeen:=true.B}
    // In bypass, initialization is always the external-pin cold reset (D83).
    // Normal-mode cold initialization is POR until a held brownout is observed.
    causes:=Cat(pinSeen || bypass,brownSeen,!bypass && !brownSeen)
  }
}
