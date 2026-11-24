package deadhorse.osc_ctrl

import chisel3._
import _root_.circt.stage.ChiselStage

/** Cold start with no assumed flop initialization or external reset pulse.
  * A real asserted POR with the bypass pad low must reach cold-only state. */
class PorBootstrapInitial extends RawModule {
  val clock=IO(Input(Clock()))
  val d=Module(new ResetBootstrap)
  d.rcClock:=clock;d.externalAonClock:=clock
  d.externalReset_n:=true.B;d.supplyReset_n:=false.B
  d.selectExternal:=false.B;d.bypassPor:=false.B
  withClockAndReset(clock,false.B) {
    assert(!d.coldReset_n)
    assert(!d.aonReset_n)
  }
}
object EmitPorBootstrapInitial extends App {
  require(args.length==1)
  ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new PorBootstrapInitial),
    Array("--target-dir",args(0)),Array("--disable-all-randomization","--disable-opt",
      "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
