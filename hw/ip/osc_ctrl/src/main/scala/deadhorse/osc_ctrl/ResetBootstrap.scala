package deadhorse.osc_ctrl

import chisel3._
import chisel3.util._
import deadhorse.lib._

/** D84 POR_BYPASS is a static board strap, fixed throughout a powered session.
  * It directly selects the reset source, independent of uninitialized state.
  * AON_CLK_SEL is sampled under that reset and then frozen. Fallback holds
  * external reset with the selected clock running; normal boot uses real POR. */
class ResetBootstrap(stableEdges: Int=8,qualifiedResets: Boolean=false) extends RawModule {
  protected def coldSource(value: Bool): Bool=value
  protected def clockSelection(held: Bool,raw: Bool): Bool=held
  protected def qualifiedRelease(value: Bool,raw: Bool): Bool=value
  require(stableEdges>=4)
  val rcClock=IO(Input(Clock()));val externalAonClock=IO(Input(Clock()))
  val externalReset_n=IO(Input(Bool()));val supplyReset_n=IO(Input(Bool()))
  val selectExternal=IO(Input(Bool()));val bypassPor=IO(Input(Bool()))
  val aonClock=IO(Output(Clock()));val aonReset_n=IO(Output(Bool()))
  val coldReset_n=IO(Output(Bool()));val warmReset_n=IO(Output(Bool()))
  val selectedExternal=IO(Output(Bool()));val selectedBypass=IO(Output(Bool()))
  val strapsFrozen=IO(Output(Bool()))
  val releases=if(qualifiedResets) Some(IO(Input(new Bundle {val cold=Bool();val pin=Bool()}))) else None

  val frozen=Wire(Bool());val sampledSelect=Wire(Bool())
  val select=clockSelection(Mux(frozen,sampledSelect,selectExternal),selectExternal)
  val bypass=bypassPor
  val selected=Mux(select,externalAonClock.asBool,rcClock.asBool).asClock
  // D83 initializes cold-only state without trusting the bypassed POR.
  val cold=coldSource(Mux(bypass,externalReset_n,supplyReset_n))
  val raw=externalReset_n && cold
  val released=releases.map(_.pin).getOrElse {
    val r=Module(new ResetRelease);r.clk:=selected;r.reset_n:=raw;r.released
  }
  val stateReset=releases.map(_.cold).getOrElse(raw)
  withClockAndReset(selected,(!stateReset).asAsyncReset) {
    val locked=RegInit(false.B)
    when(released) {locked:=true.B}
    frozen:=locked && (if(qualifiedResets) released else true.B)
    val edges=RegInit(0.U(log2Ceil(stableEdges+1).W))
    when(locked && edges<stableEdges.U) {edges:=edges+1.U}
    if(qualifiedResets) when(!released) {locked:=false.B;edges:=0.U}
    aonReset_n:=qualifiedRelease(released && locked && edges===stableEdges.U,raw)
  }
  // Intentionally outside the reset they help select. They are always sampled
  // before locked can assert; no consumers leave reset before qualification.
  withClockAndReset(selected,false.B) {
    val clockStrap=Reg(Bool())
    when(!frozen) {clockStrap:=selectExternal}
    sampledSelect:=clockStrap
  }
  aonClock:=selected;coldReset_n:=cold;warmReset_n:=externalReset_n
  selectedExternal:=select;selectedBypass:=bypass;strapsFrozen:=frozen
}
