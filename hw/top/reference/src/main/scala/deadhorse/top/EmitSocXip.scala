package deadhorse.top
import _root_.circt.stage.ChiselStage
import deadhorse.lib.ClockGateTarget
object SocXipFiles {
  def config(mhz: Int=8,usb: Boolean=false): SocI1Config=
    SocQspiFiles.config(mhz,usb).copy(qspi=Some("build/t30/qspi/qspi_regs.json"),xip=true)
}
object EmitSocXip extends App {
  require(args.length==3,"EmitSocXip <output-under-build> <stub|usb> <8|9>")
  require(args(0).startsWith("build/") && !args(0).contains("..") && Set("stub","usb").contains(args(1)))
  val c=SocXipFiles.config(args(2).toInt,args(1)=="usb")
  ChiselStage.emitSystemVerilogFile(new DeadhorseSoc("build/t20/map/soc.json",c.uart,
    "build/t20/i0-firmware/boot.hex",gateTarget=ClockGateTarget.Asic,i1Config=Some(c)),
    Array("--target-dir",args(0)),Array("--disable-all-randomization","--strip-debug-info",
    "--preserve-values=named","--verification-flavor=immediate","--lower-to-core"))
}
object EmitXipMemory extends App {
  require(args.length==1 && args(0).startsWith("build/") && !args(0).contains(".."))
  ChiselStage.emitSystemVerilogFile(new SocLocalMemory(new SocDescription("build/t20/map/soc.json"),
    "build/t20/i0-firmware/boot.hex",dmaEnabled=true,xipEnabled=true),Array("--target-dir",args(0)),
    Array("--disable-all-randomization","--strip-debug-info","--preserve-values=named",
      "--verification-flavor=immediate","--lower-to-core"))
}
