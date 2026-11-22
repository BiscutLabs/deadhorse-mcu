package deadhorse.top
import _root_.circt.stage.ChiselStage
import deadhorse.lib.ClockGateTarget
object SocPwmFiles {
  def config(mhz: Int=8,usb: Boolean=false): SocI1Config=
    SocIoFiles.config(mhz,usb).copy(pwm=Some("build/t22/pwm/pwm_regs.json"))
}
object EmitSocPwm extends App {
  require(args.length==4,"EmitSocPwm <output-under-build> <peripherals|soc> <stub|usb> <8|9>")
  require(args(0).startsWith("build/") && !args(0).contains("..") && Set("stub","usb").contains(args(2)))
  val c=SocPwmFiles.config(args(3).toInt,args(2)=="usb")
  ChiselStage.emitSystemVerilogFile(if(args(1)=="peripherals") {
    new SocI1Peripherals(new SocDescription("build/t20/map/soc.json"),c)
  } else {
    require(args(1)=="soc")
    new DeadhorseSoc("build/t20/map/soc.json",c.uart,"build/t20/i0-firmware/boot.hex",
      gateTarget=ClockGateTarget.Asic,i1Config=Some(c))
  },Array("--target-dir",args(0)),Array("--disable-all-randomization","--strip-debug-info",
    "--preserve-values=named","--verification-flavor=immediate","--lower-to-core"))
}
