package deadhorse.top
import _root_.circt.stage.ChiselStage
import deadhorse.lib.ClockGateTarget
object SocIoFiles {
  def config(mhz: Int=8,usb: Boolean=false): SocI1Config=SocI1Files.config(usb).copy(io=Some(SocIoConfig(
    "build/t21/gpio/gpio_regs.json","build/t21/timers/timers_regs.json",
    "build/t21/aon_timer/aon_timer_regs.json","build/t21/adc/adc_regs.json",mhz)))
}
object EmitSocIo extends App {
  require(args.length==4,"EmitSocIo <output-under-build> <peripherals|soc> <stub|usb> <8|9>")
  require(args(0).startsWith("build/") && !args(0).contains("..") && Set("stub","usb").contains(args(2)))
  val c=SocIoFiles.config(args(3).toInt,args(2)=="usb")
  val options=Array("--disable-all-randomization","--strip-debug-info","--preserve-values=named",
    "--verification-flavor=immediate","--lower-to-core")
  ChiselStage.emitSystemVerilogFile(if(args(1)=="peripherals") {
    new SocI1Peripherals(new SocDescription("build/t20/map/soc.json"),c)
  } else {
    require(args(1)=="soc")
    new DeadhorseSoc("build/t20/map/soc.json",c.uart,"build/t20/i0-firmware/boot.hex",
      gateTarget=ClockGateTarget.Asic,i1Config=Some(c))
  },Array("--target-dir",args(0)),options)
}
