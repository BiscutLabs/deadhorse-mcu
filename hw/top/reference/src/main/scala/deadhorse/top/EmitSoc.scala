package deadhorse.top

import _root_.circt.stage.ChiselStage
import deadhorse.lib.ClockGateTarget

object EmitSoc extends App {
  require(args.length==3,"EmitSoc <output-under-build> <production|usb-stub-test> <8|9>")
  require(args(0).startsWith("build/") && !args(0).contains(".."))
  require(Set("production","usb-stub-test").contains(args(1)) && args(2)=="8")
  val c=SocProduction.config(args(2).toInt,args(1)=="production")
  ChiselStage.emitSystemVerilogFile(new DeadhorseSoc("build/t20/map/soc.json",c.uart,
    "build/t20/i0-firmware/boot.hex",gateTarget=ClockGateTarget.Asic,i1Config=Some(c)),
    Array("--target-dir",args(0)),Array("--disable-all-randomization","--strip-debug-info",
      "--preserve-values=named","--verification-flavor=immediate","--lower-to-core"))
}

/** Historical independent-clock tests retain both operating points. */
object EmitSocExternalClockTest extends App {
  require(args.length==3 && args(0).startsWith("build/") && !args(0).contains(".."))
  require(Set("production","usb-stub-test").contains(args(1)))
  val c=SocProduction.config(args(2).toInt,args(1)=="production")
  ChiselStage.emitSystemVerilogFile(new SocExternalClockTest("build/t20/map/soc.json",c.uart,
    "build/t20/i0-firmware/boot.hex",gateTarget=ClockGateTarget.Asic,i1Config=Some(c)),
    Array("--target-dir",args(0)),Array("--disable-all-randomization","--strip-debug-info",
      "--preserve-values=named","--verification-flavor=immediate","--lower-to-core"))
}
