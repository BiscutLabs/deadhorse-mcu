package deadhorse.top
import _root_.circt.stage.ChiselStage

object EmitDmaMemory extends App {
  require(args.length==1 && args(0).startsWith("build/") && !args(0).contains(".."))
  ChiselStage.emitSystemVerilogFile(new SocLocalMemory(new SocDescription("build/t20/map/soc.json"),
    "build/t20/i0-firmware/boot.hex",dmaEnabled=true),Array("--target-dir",args(0)),
    Array("--disable-all-randomization","--strip-debug-info","--preserve-values=named",
      "--verification-flavor=immediate","--lower-to-core"))
}

object EmitXipMemory extends App {
  require(args.length==1 && args(0).startsWith("build/") && !args(0).contains(".."))
  ChiselStage.emitSystemVerilogFile(new SocLocalMemory(new SocDescription("build/t20/map/soc.json"),
    "build/t20/i0-firmware/boot.hex",dmaEnabled=true,xipEnabled=true),Array("--target-dir",args(0)),
    Array("--disable-all-randomization","--strip-debug-info","--preserve-values=named",
      "--verification-flavor=immediate","--lower-to-core"))
}
