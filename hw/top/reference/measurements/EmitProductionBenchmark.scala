package deadhorse.top
import _root_.circt.stage.ChiselStage
import deadhorse.lib.ClockGateTarget
object EmitProductionBenchmark extends App {
  require(args.length==3)
  val c=SocProduction.config(args(2).toInt,true)
  ChiselStage.emitSystemVerilogFile(new DeadhorseSoc("build/t20/map/soc.json",c.uart,
    args(1),gateTarget=ClockGateTarget.Model,i1Config=Some(c)),
    Array("--target-dir",args(0)),Array("--disable-all-randomization","--strip-debug-info",
      "--preserve-values=named","--verification-flavor=immediate","--lower-to-core",
      "--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
      "--ckg-enable=en_i","--ckg-test-enable=test_en_i"))
}
