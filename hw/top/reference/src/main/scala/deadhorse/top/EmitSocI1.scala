package deadhorse.top

import circt.stage.ChiselStage
import deadhorse.lib.ClockGateTarget

object SocI1Files {
  val root="build/t20/i1"
  def config(realUsb: Boolean=false): SocI1Config=SocI1Config(
    s"$root/uart/uart_regs.json",s"$root/spi_host/spi_host_regs.json",s"$root/i2c_host/i2c_host_regs.json",
    s"$root/mailbox/mailbox_regs.json",s"$root/usb/usb_regs.json",realUsb)
}
object EmitSocI1 extends App {
  require(args.length==3,"EmitSocI1 <output-under-build> <peripherals|soc> <stub|usb>")
  require(args(0).startsWith("build/") && !args(0).contains(".."))
  val config=SocI1Files.config(args(2)=="usb")
  require(Set("stub","usb").contains(args(2)))
  val options=Array("--disable-all-randomization","--strip-debug-info","--preserve-values=named",
    "--verification-flavor=immediate","--lower-to-core")
  if(args(1)=="peripherals") ChiselStage.emitSystemVerilogFile(
    new SocI1Peripherals(new SocDescription("build/t20/map/soc.json"),config),
    Array("--target-dir",args(0)),options)
  else {
    require(args(1)=="soc")
    ChiselStage.emitSystemVerilogFile(new DeadhorseSoc("build/t20/map/soc.json",config.uart,
      "build/t20/i0-firmware/boot.hex",gateTarget=ClockGateTarget.Asic,i1Config=Some(config)),
      Array("--target-dir",args(0)),options)
  }
}
