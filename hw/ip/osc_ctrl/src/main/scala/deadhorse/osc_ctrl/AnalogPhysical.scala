package deadhorse.osc_ctrl

import chisel3._
import deadhorse.lib.ResetRelease

/** D111 physical LF readiness; analog initialization must be qualified separately.
  * Four fresh source edges, with the first two in the shared reset-release cell.
  * No oscillator is synthesized by this module.
  */
class LfReadyPhysical extends RawModule {
  protected def qualifiedReady(third: Bool,fourth: Bool): Bool=fourth
  val source=IO(Input(Clock()))
  val power_n=IO(Input(Bool()))
  val enable=IO(Input(Bool()))
  val ready=IO(Output(Bool()))
  val release=Module(new ResetRelease)
  release.clk:=source
  release.reset_n:=power_n && enable
  // Share the initializer across all flops. The synchronized indication is
  // data, avoiding a same-clock reset-removal boundary between the stages.
  withClockAndReset(source,(!(power_n && enable)).asAsyncReset) {
    val third=RegInit(false.B)
    val fourth=RegInit(false.B)
    third:=release.released
    fourth:=third
    ready:=qualifiedReady(third,fourth)
  }
}

object EmitAnalogPhysical extends App {
  require(args.length==1)
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(new LfReadyPhysical,
    Array("--target-dir",args(0)),Array("--disable-all-randomization",
      "--strip-debug-info","--preserve-values=named","--lower-to-core"))
}
