package deadhorse.top

import circt.stage.ChiselStage
import java.nio.file.{Files,Paths}

object EmitSocFixture extends App {
  require(args.length==2,"fixture-directory output-directory")
  val input=Paths.get(args(0)).toAbsolutePath.normalize
  val output=Paths.get(args(1)).toAbsolutePath.normalize
  val build=Paths.get("build").toAbsolutePath.normalize
  require(input.startsWith(build) && output.startsWith(build))
  Files.createDirectories(output)
  ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new SocMinimalI0(input.resolve("soc.json").toString,
    input.resolve("uart_regs.json").toString,input.resolve("rom.hex").toString,
    verificationFixture=true,ramImages=(0 until 4).map(i=>input.resolve(s"ram$i.hex").toString))),
    Array("--target-dir",output.toString),Array("--disable-all-randomization","-strip-debug-info",
      "--verification-flavor=immediate","--lower-to-core",
      "--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
      "--ckg-enable=en_i","--ckg-test-enable=test_en_i"))
}
