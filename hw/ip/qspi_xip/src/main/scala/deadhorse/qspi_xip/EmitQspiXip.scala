package deadhorse.qspi_xip
object EmitQspiXip extends App {
  require(args.length==1)
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(
    new deadhorse.qspi.Qspi("build/t30/qspi/qspi_regs.json",withXip=true),Array("--target-dir",args(0)),
    Array("--disable-all-randomization","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
