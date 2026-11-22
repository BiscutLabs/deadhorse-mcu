package deadhorse.watchdog
import _root_.circt.stage.ChiselStage
object EmitWatchdogBindings extends App {
  require(args.length==2)
  ChiselStage.emitSystemVerilogFile(args(0) match {
    case "watchdog"=>new Watchdog("build/t26/watchdog/watchdog_regs.json")
    case "pwm"=>new deadhorse.pwm.Pwm("build/t22/pwm/pwm_regs.json",watchdog=true)
    case "pinmux"=>new deadhorse.pinmux.Pinmux("build/t24/pinmux/pinmux_regs.json",watchdog=true)
  },Array("--target-dir",args(1)),Array("--disable-all-randomization","--strip-debug-info",
    "--verification-flavor=immediate","--lower-to-core"))
}
