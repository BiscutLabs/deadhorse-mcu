package deadhorse.top

/** T43 fixture: existing analog model substitution, real production features.
  * The pad adapter and foundry pad models remain outside the Chisel core. */
object EmitPadModel extends App {
  require(args.length == 1 && args(0).startsWith("build/") && !args(0).contains(".."))
  val c = SocProduction.config()
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(
    new SocAnalogModelTest("build/t20/map/soc.json", c.uart, "build/t36/rom/rom.hex"),
    Array("--target-dir", args(0)), Array("--disable-all-randomization", "--strip-debug-info",
      "--preserve-values=named", "--verification-flavor=immediate", "--lower-to-core",
      "--ckg-name=prim_generic_clock_gating", "--ckg-input=clk_i", "--ckg-output=clk_o",
      "--ckg-enable=en_i", "--ckg-test-enable=test_en_i"))
}
