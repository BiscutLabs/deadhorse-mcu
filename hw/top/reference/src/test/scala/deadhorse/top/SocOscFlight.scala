package deadhorse.top

import chisel3._
import _root_.circt.stage.ChiselStage

/** Passive RVFI observations of the unchanged production assembly. */
class SocOscFlight(rom: String) extends SocAnalogModelTest(
    "build/t20/map/soc.json",SocProduction.config().uart,rom) {
  val rvfi=digital.rvfi.toSeq.map { case(name,signal)=>
    val port=IO(Output(chiselTypeOf(signal))).suggestName(name)
    port:=signal;name->port
  }.toMap
}

object EmitOscFlight extends App {
  require(args.length==2)
  ChiselStage.emitSystemVerilogFile(new SocOscFlight(args(1)),
    Array("--target-dir",args(0)),Array("--disable-all-randomization","--strip-debug-info",
      "--preserve-values=named","--verification-flavor=immediate","--lower-to-core",
      "--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
      "--ckg-enable=en_i","--ckg-test-enable=test_en_i"))
}
