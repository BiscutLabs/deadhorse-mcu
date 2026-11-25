package deadhorse.top
import _root_.circt.stage.ChiselStage
import deadhorse.lib.ClockGateTarget
import deadhorse.perf_core.IbexTop
import deadhorse.lite_core.LiteHart

/** Identical production core parameters; only the observation interface varies. */
object EmitRvfiVariants extends App {
  require(args.length==1)
  val options=Array("--disable-all-randomization","--strip-debug-info","--preserve-values=named",
    "--verification-flavor=immediate","--lower-to-core")
  for(trace<-Seq(true,false)) {
    val side=if(trace) "verification" else "production"
    ChiselStage.emitSystemVerilogFile(new LiteHart(withDebug=true,withRVFI=trace),
      Array("--target-dir",s"${args(0)}/lite/$side"),options)
    ChiselStage.emitSystemVerilogFile(new IbexTop(ClockGateTarget.Model,WithRVFI=trace,
      RegisteredExecution=false,WithF=true,DmHaltAddr=0x10800,DmExceptionAddr=0x10810),
      Array("--target-dir",s"${args(0)}/performance/$side"),options++Array(
        "--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
        "--ckg-enable=en_i","--ckg-test-enable=test_en_i"))
  }
}
