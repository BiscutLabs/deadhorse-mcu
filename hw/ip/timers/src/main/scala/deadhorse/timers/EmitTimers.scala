package deadhorse.timers
import _root_.circt.stage.ChiselStage
import deadhorse.aon_timer.AonTimers
object EmitTimers extends App {
  require(args.length==4,"EmitTimers <main|aon> <regmap-json> <output> <mainMHz>")
  ChiselStage.emitSystemVerilogFile(
    if(args(0)=="main") new GeneralTimers(args(1),args(3).toInt) else {
      require(args(0)=="aon");new AonTimers(args(1))
    },Array("--target-dir",args(2)),
    Array("--disable-all-randomization","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
