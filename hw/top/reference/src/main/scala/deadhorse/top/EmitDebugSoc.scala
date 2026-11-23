package deadhorse.top
import chisel3._
import deadhorse.lib.ClockGateTarget
/** Production features and actual TAP, with the project's simulation clock-cell model. */
object EmitDebugSoc extends App {
  require((args.length==1 || args.length==2) && args(0).startsWith("build/") && !args(0).contains(".."))
  val variant=if(args.length==2) args(1) else "correct"
  require(Set("correct","missing-halt").contains(variant))
  val c=SocProduction.config()
  def design: DeadhorseSoc=if(variant=="missing-halt") new DeadhorseSoc("build/t20/map/soc.json",c.uart,
    "build/t20/i0-firmware/boot.hex",gateTarget=ClockGateTarget.Model,i1Config=Some(c)) {
      override def desiredName="DeadhorseSoc"
      override protected def debugRequest(request: Bool): Bool=false.B
    } else new DeadhorseSoc("build/t20/map/soc.json",c.uart,
      "build/t20/i0-firmware/boot.hex",gateTarget=ClockGateTarget.Model,i1Config=Some(c))
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(design),
    Array("--target-dir",args(0)),Array("--disable-all-randomization","--strip-debug-info",
      "--preserve-values=named","--verification-flavor=immediate","--lower-to-core",
      "--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
      "--ckg-enable=en_i","--ckg-test-enable=test_en_i"))
}
